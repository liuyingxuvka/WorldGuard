"""Resolve original-file pointers and compare the AI transcription with visible text."""

from __future__ import annotations

import csv
import hashlib
import re
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from .clock import time_kind, time_key
from .errors import WorldInputError
from .io import _read, input_digests
from .relations import parse_relations
from .source_readers import (
    norm,
    uses_24h,
    decimal_evidence,
    CELL_TIME,
    CLOCK,
    AMPM,
    times_in,
    sentences,
    time_mentions,
    date_mentions,
    date_matches,
    show_date,
    show_cands,
    hm,
    strip_times_dates,
    quantities,
    unit_info,
    fmt,
)
from .variants import _select_path, apply_variant
from .status import GuardStatus, aggregate_statuses

POINTER = re.compile(
    r'^(?P<label>[\w.-]+)\s+(?:p(?P<para>\d+)|r(?P<row>\d+)\s+(?P<col>[\w.-]+))(?:\s+"(?P<quote>[^"]*)")?\s*$'
)
SOURCE_FIELDS = frozenset({"texts", "aliases", "tables", "decimal", "values"})


def source_config(data):
    config = {key: deepcopy(data[key]) for key in SOURCE_FIELDS if key in data}
    for key, value in config.items():
        if not isinstance(value, dict):
            raise WorldInputError(f"{key} must be a mapping")
    for label, value in config.get("texts", {}).items():
        if not isinstance(label, str) or not isinstance(value, str):
            raise WorldInputError("texts must map source labels to file paths")
    for name, aliases in config.get("aliases", {}).items():
        if not isinstance(name, str) or not isinstance(aliases, list) or any(not isinstance(a, str) for a in aliases):
            raise WorldInputError("aliases must map names to lists of strings")
    for label, table in config.get("tables", {}).items():
        if not isinstance(table, dict) or set(table) - {"header_rows"}:
            raise WorldInputError(f"tables.{label} accepts only header_rows")
        if type(table.get("header_rows", 1)) is not int or table.get("header_rows", 1) < 1:
            raise WorldInputError(f"tables.{label}.header_rows must be a positive integer")
    if any(not isinstance(value, str) or value not in {".", ","} for value in config.get("decimal", {}).values()):
        raise WorldInputError("decimal values must be dot or comma")
    return config


def load_texts(config, base_dir):
    return {
        label: Text(
            label,
            Path(base_dir) / path,
            config.get("tables", {}).get(label, {}).get("header_rows", 1),
            config.get("decimal", {}).get(label),
        )
        for label, path in config.get("texts", {}).items()
    }


class Text:
    def __init__(self, label: str, path: Path, header_rows: int = 1, decimal: str | None = None):
        self.label, self.path, self.header_rows = label, path, header_rows
        raw = _read(path, path.read_bytes)
        self.sha = hashlib.sha256(raw).hexdigest()
        self.kind = "csv" if path.suffix.lower() == ".csv" else "prose"
        decoded = _read(path, lambda: raw.decode("utf-8"))
        cells = (
            decoded
            if path.suffix.lower() != ".csv"
            else " ".join(c for line in csv.reader(decoded.splitlines()) for c in line if not CELL_TIME.match(c))
        )
        self.decimal, self.decimal_declared = (decimal, True) if decimal else (decimal_evidence(cells), False)
        if self.kind == "csv":
            lines = list(csv.reader(decoded.splitlines()))
            head, body = lines[:header_rows], lines[header_rows:]
            for row in head[:-1]:  # merged cells: a blank header cell belongs to the label on its left
                for i in range(1, len(row)):
                    if not row[i].strip():
                        row[i] = row[i - 1]
            width = max((len(r) for r in head), default=0)
            names = [
                ".".join(dict.fromkeys(r[i].strip() for r in head if i < len(r) and r[i].strip())) for i in range(width)
            ]
            if header_rows > 1:
                names = [n.lower() for n in names]
            self.columns = names
            self.rows = [dict(zip(names, r)) for r in body if any(c.strip() for c in r)]
            self.units = len(self.rows)
        else:
            self.conv24 = uses_24h(decoded)
            blocks = [b.strip() for b in re.split(r"\n\s*\n", decoded)]
            self.paras, self.heads, heading = [], [], ""
            for b in blocks:
                if not b:
                    continue
                if b.startswith("#"):
                    heading = " ".join(b.lstrip("#").split())
                    continue
                # collapse line breaks and ASCII blanks only: a thin or no-break space inside a number is kept
                self.paras.append(re.sub(r"[ \t\r\n\f\v]+", " ", b).strip())
                self.heads.append(heading)
            self.units = len(self.paras)

    def unit_text(self, n: int) -> str:
        return " | ".join(f"{k}={v}" for k, v in self.rows[n - 1].items()) if self.kind == "csv" else self.paras[n - 1]

    def unit_times(self, n: int) -> list[int]:
        """Times a paragraph or a table row states (a row's cells are read as cells, so 18.25 counts)."""
        if self.kind == "prose":
            return times_in(self.paras[n - 1])
        cells = [CELL_TIME.match(v) for v in self.rows[n - 1].values()]
        return sorted({int(m[1]) * 60 + int(m[2]) for m in cells if m} | set(times_in(self.unit_text(n))))

    def column(self, name: str) -> str | None:
        for col in self.columns:
            if col == name or col.lower() == name.lower():
                return col
        return None


def named_at(name: str, text: str, aliases: dict) -> tuple[str, int] | None:
    """The word that names `name` in the text (the name or a declared alias) and where, or None."""
    text = norm(text)
    best = None
    for word in [name, *aliases.get(name, [])]:
        match = re.search(rf"(?<![\w.]){re.escape(norm(str(word).replace('_', ' ')))}(?![\w]|\.\d)", text, re.I)
        if match and (best is None or match.start() < best[1]):
            best = (str(word), match.start())
    return best


def named(name: str, text: str, aliases: dict) -> str | None:
    hit = named_at(name, text, aliases)
    return hit[0] if hit else None


CODE_DOTTED = re.compile(r"(?<![\w.])v?(\d+(?:\.\d+)+)(?![\w]|\.\d)", re.I)
CODE_LETTERS = re.compile(r"(?<![\w])([A-Z]{1,4})[ _-]?(\d{1,5})(?!\w)", re.I)


def code_shape(name: str):
    """('dotted', groups) for 4.2.1 or v4.2.1, ('letters', prefix) for F15 or IC 2215, else None."""
    text = str(name).replace("_", ".")
    if re.fullmatch(r"v?\d+(?:\.\d+)+", text, re.I):
        return "dotted", text.lstrip("vV").count(".") + 1
    match = re.fullmatch(r"([A-Za-z]{1,4})[ .-]?(\d{1,5})", text)
    if match:
        return "letters", match[1].upper()
    return None


def codes_in(text: str, shape) -> list[str]:
    text = strip_times_dates(norm(text))
    if shape[0] == "dotted":
        return [m[1] for m in CODE_DOTTED.finditer(text) if m[1].count(".") + 1 == shape[1]]
    return [f"{m[1]}{m[2]}" for m in CODE_LETTERS.finditer(text) if m[1].upper() == shape[1]]


# ---------- feature A: readings ----------


def world_names(contract: dict) -> tuple[set, set, set]:
    persons, things, places = set(), set(), set()
    for kind, subject, obj in parse_relations(contract.get("world_model", {}).get("relations", {})).values():
        persons.add(subject)
        (things if kind == "holds" else places).add(obj)
    for event in contract.get("inputs", {}).get("events", []):
        if event.get("actor"):
            persons.add(event["actor"])
        persons.update(event.get("with", []) or [])
        uses = event.get("uses", []) or []
        things.update([uses] if isinstance(uses, str) else uses)
        if event.get("place"):
            places.add(event["place"])
    return persons, things, places


def at_parts(at):
    """(kind, date or None, minutes) for a clock or ISO time; (kind, None, None) when the clock is labels or numbers."""
    kind = time_kind(at)
    if kind == "clock":
        return kind, None, int(time_key(at)) // 60
    if kind == "ISO date-time":
        stamp = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
        return kind, stamp.date().isoformat(), stamp.hour * 60 + stamp.minute
    return kind, None, None


def resolve(pointer, texts: dict, cited: dict, add) -> dict | None:
    """The span a pointer names: {'text', 'n', 'span', 'quote', 'cell', 'row'}; None (with a reading) when it names nothing."""
    match = POINTER.match(str(pointer))
    if not pointer:
        add("span", ".", "no source")
        return None
    if not match or match["label"] not in texts:
        add("span", ".", f'source "{pointer}" is free text; nothing to read')
        return None
    text = texts[match["label"]]
    n = int(match["para"] or match["row"])
    if (match["para"] and text.kind != "prose") or (match["row"] and text.kind != "csv"):
        add("span", "R", f"{match['label']} is {text.kind}; pointer {pointer!r} does not fit")
        return None
    if not 1 <= n <= text.units:
        add("span", "R", f"{match['label']} has no {'p' if match['para'] else 'r'}{n} ({text.units} in the file)")
        return None
    cited.setdefault(match["label"], set()).add(n)
    out = {"text": text, "n": n, "quote": match["quote"], "label": match["label"]}
    if text.kind == "csv":
        row = text.rows[n - 1]
        col = text.column(match["col"])
        if col is None:
            add(
                "span",
                "R",
                f"{match['label']} has no column {match['col']}"
                + (f" (columns: {', '.join(c for c in text.columns if c)})" if text.header_rows > 1 else ""),
            )
            return None
        out["cell"], out["row"], out["col"] = row[col], row, col
        date_col = next((c for c in row if c.lower() == "date"), None)
        out["span_date_text"] = row[date_col] if date_col else None
        key = next(iter(row.values()), "")
        out["span"] = (
            f"{match['label']} r{n}"
            + (f" ({key})" if text.header_rows > 1 else "")
            + f" {col}={row[col]}"
            + (f" date={out['span_date_text']}" if date_col else "")
        )
    else:
        out["span"] = text.paras[n - 1]
        if match["quote"] is not None and norm(match["quote"]) not in norm(out["span"]):
            add("quote", "R", f'not in {match["label"]} p{n}: "{match["quote"]}"')
            out["quote_missing"] = True
    return out


def mentions_with_dates(res: dict) -> list[tuple[set[int], list]]:
    """Each time the span states, with the date that goes with it: the date of its own sentence, else of the paragraph
    (when it states one), else of the heading above (when it states one); a CSV cell takes its row's date column."""
    text = res["text"]
    if text.kind == "csv":
        cell = res["cell"]
        match = CELL_TIME.match(cell)
        cands = [({int(match[1]) * 60 + int(match[2])}, 0)] if match else time_mentions(cell)
        dates = date_mentions(res["span_date_text"]) if res.get("span_date_text") else []
        return [(c, dates) for c, _ in cands]
    span = res["span"]
    sents = sentences(span)
    para_dates = list(dict.fromkeys(date_mentions(res.get("paragraph_span", span))))
    head_dates = list(dict.fromkeys(date_mentions(text.heads[res["n"] - 1])))
    out = []
    for cands, index in time_mentions(span, text.conv24):
        own = list(dict.fromkeys(date_mentions(sents[index]))) if index < len(sents) else []
        out.append(
            (cands, own or (para_dates if len(para_dates) == 1 else []) or (head_dates if len(head_dates) == 1 else []))
        )
    return out


# Finite source bindings, shared by ordinary and mesh source evidence.
_ORDINAL = re.compile(
    r"^\s+(?:takes?|catches?|boards?|chooses?|uses?|rides?)\s+(?:the\s+)?"
    r"(first|second|third|last|former|latter)\b", re.I,
)
_TRANSFER_PASSIVE = re.compile(
    r"\b(?:is|are|was|were)\s+(?:(?:being|been)\s+)?(?:handed|given|passed|transferred)\b", re.I,
)
_ACTIVE_EVENT = re.compile(
    r"^\s+(?:hands?|gives?|passes?|transfers?|opens?|closes?|locks?|unlocks?|boards?|takes?|"
    r"catches?|chooses?|uses?|rides?|arrives?|departs?|leaves?|enters?|starts?|packs?)\b", re.I,
)


def _event_time_binding(res, event, aliases):
    """Bind a finite named event/ordinal, rather than accepting any value in its paragraph."""
    original = mentions_with_dates(res)
    span = norm(res['span'])
    if res['text'].kind == 'csv':
        return original, span, '', '', False
    pointer = POINTER.match(str(event.get('source', '')))
    quote = pointer['quote'] if pointer and not res.get('quote_missing') else None
    if quote and time_mentions(quote, res['text'].conv24):
        span = norm(quote)
    clauses = [part.strip() for sentence in sentences(span) for part in sentence.split(';') if part.strip()]
    actor = event.get('actor')

    def mentions(part):
        return mentions_with_dates({**res, 'span': part, 'paragraph_span': res['span']})

    available = mentions(span)
    if len(available) == 1 and len(available[0][0]) == 1:
        return available, span, '', '', False
    if re.search(r'\b(?:between\s+\d{1,2}:\d{2}\s+and|from\s+\d{1,2}:\d{2}\s+(?:to|until))\b', span, re.I) and len(available) > 1:
        return available, span, 'cannot bind one event time in an interval: ' + ', '.join(show_cands(c) for c, _ in available), '', True
    selections = []
    for index, clause in enumerate(clauses):
        hit = named_at(actor, clause, aliases) if actor else None
        if hit:
            end = hit[1] + len(norm(hit[0].replace('_', ' ')))
            if choice := _ORDINAL.match(clause[end:]):
                selections.append((index, choice[1].lower(), clause[:hit[1]]))
    if len(selections) == 1:
        index, ordinal, prefix = selections[0]
        own = mentions(clauses[index])
        if len(own) == 1 and len(own[0][0]) == 1:
            return own, clauses[index], '', f' (explicit time for {actor})', False
        pool = prefix if len(CLOCK.findall(prefix)) + len(AMPM.findall(prefix)) >= 2 else clauses[index - 1] if index else ''
        options = mentions(pool) if pool else []
        numeric = len(CLOCK.findall(pool)) + len(AMPM.findall(pool)) == len(options)
        unique = len({next(iter(candidates)) for candidates, _ in options if len(candidates) == 1}) == len(options)
        if 2 <= len(options) <= 3 and numeric and unique and all(len(c) == 1 for c, _ in options):
            chosen = {'first': 0, 'second': 1, 'third': 2, 'last': len(options) - 1,
                      'former': 0, 'latter': 1}[ordinal]
            if chosen < len(options) and (ordinal not in ('former', 'latter') or len(options) == 2):
                return [options[chosen]], clauses[index], '', f' ({ordinal} of {len(options)} departures for {actor})', False
        return original, clauses[index], f'cannot bind {actor} to {ordinal}: need one ordered list of 2-3 explicit clock times', '', False
    if len(selections) > 1:
        return original, span, f'cannot bind {actor}: several event selections in this span', '', False
    timed_actor = [clause for clause in clauses if actor and named(actor, clause, aliases) and mentions(clause)]
    selected_span = timed_actor[0] if len(timed_actor) == 1 else span
    found = mentions(selected_span)
    signatures = {(tuple(sorted(c)), tuple(dates)) for c, dates in found}
    if len(signatures) > 1 or any(len(c) > 1 for c, _ in found):
        choices = ', '.join(show_cands(c) for c, _ in found)
        return found, selected_span, f'cannot bind one event time: candidates {choices}; name the event or its choice', '', False
    return found, selected_span, '', '', False

def _event_actor_binding(span, actor, persons, aliases):
    """Only explicit named subjects or the finite passive transfer agent establish the role."""
    hits = {person: hit for person in persons if (hit := named_at(person, span, aliases))}
    if passive := _TRANSFER_PASSIVE.search(span):
        tail = re.split(r'\bby\b', span[passive.end():], maxsplit=1, flags=re.I)
        if len(tail) == 2:
            agent_text = norm(tail[1])
            agents = [(person, hit) for person in persons if (hit := named_at(person, agent_text, aliases))]
            if len(agents) == 1:
                person, (word, start) = agents[0]
                end = start + len(norm(word.replace('_', ' ')))
                prefix = re.fullmatch(r'\s*(?:(?:Dr|Mr|Mrs|Ms)\.?\s*)?', agent_text[:start], re.I)
                suffix = re.match(r'\s*(?:[.!?]|$|\b(?:at|in|on)\s)', agent_text[end:], re.I)
                if prefix and suffix:
                    return person, ''
        return None, 'cannot bind transfer agent: passive transfer needs one named by-agent'
    if re.search(r'\b(?:is|are|was|were)\b.*\bby\b', span, re.I) and len(hits) > 1:
        return None, 'cannot bind actor: passive role is outside the supported transfer forms'
    if not hits:
        return None, f'{actor} not named in event span (pronoun?)'
    first = min(hits, key=lambda name: hits[name][1])
    hit = hits[first]
    suffix = span[hit[1] + len(norm(hit[0].replace('_', ' '))):]
    if len(hits) > 1 and re.match(r'^\s+(?:watches?|sees?|hears?|asks?|tells?)\b', suffix, re.I):
        return None, 'cannot bind actor through a nested observer/speech clause'
    if _ACTIVE_EVENT.match(suffix):
        return first, ''
    if first != actor and actor in hits:
        return None, f'{first} named before {actor}: who acts is not read'
    return first, ''


def table_hint(res: dict, minutes: int) -> str:
    """Where the AI's time does stand in the table: another cell of the cited row, or the cited column of another row."""
    text, n, col = res["text"], res["n"], res["col"]

    def at(cell):
        m = CELL_TIME.match(cell)
        return m and int(m[1]) * 60 + int(m[2]) == minutes

    same_row = [c for c, v in text.rows[n - 1].items() if c != col and at(v)]
    same_col = [f"r{i}" for i, row in enumerate(text.rows, 1) if i != n and at(row.get(col, ""))]
    where = [f"{c} of this row" for c in same_row] + [f"{col} of {r}" for r in same_col]
    return f" ({hm(minutes)} is in {', '.join(where)})" if where else ""


def read_event(event: dict, texts: dict, aliases: dict, names: tuple, cited: dict) -> dict:
    persons, things, places = names
    out = {
        "event": event.get("event_id"),
        "pointer": event.get("source", ""),
        "readings": [],
        "edits": {},
        "sourced": False,
        "span": None,
    }
    add = lambda field, colour, note: out["readings"].append((field, colour, note))  # noqa: E731
    res = resolve(event.get("source", ""), texts, cited, add)
    if res is None:
        return out
    text = res["text"]
    span = res["span"]
    out["span"] = span
    # time and date
    kind, at_date, at_min = at_parts(event["at"]) if "at" in event else (None, None, None)
    found, actor_span, time_ambiguity, binding_note, time_interval = _event_time_binding(res, event, aliases)
    time_ok = False
    if "at" not in event:
        add("time", ".", "event has no time")
    elif at_min is None:
        add("time", ".", f"world clock is {kind}s; nothing to compare")
    elif time_ambiguity and (time_interval or not found or any(at_min in candidates for candidates, _ in found)):
        add("time", ".", time_ambiguity)
        # A missing event/time binding must not hide a separately explicit date contradiction.
        dates = list(dict.fromkeys(date for _, dates in found for date in dates))
        if kind == "ISO date-time" and len(dates) == 1 and not date_matches(dates[0], at_date):
            add("date", "R", f"span says {show_date(dates[0])}; world says {at_date}")
            year, month, day = dates[0]
            out["edits"]["at"] = f"{year or int(at_date[:4]):04d}-{month:02d}-{day:02d}T{at_min // 60:02d}:{at_min % 60:02d}"
    elif not found:
        add("time", ".", f'span has no time; "{event["at"]}" is the AI\'s')
    else:
        iso = kind == "ISO date-time"
        full = [
            f for f in found if at_min in f[0] and (not iso or not f[1] or any(date_matches(d, at_date) for d in f[1]))
        ]
        timed = [f for f in found if at_min in f[0]]
        twelve = len(next(iter(full or timed or found))[0]) > 1
        note12 = " (12-hour, the text gives no a.m./p.m.)" if twelve and (full or timed) else ""
        if full:
            dates = full[0][1]
            if iso and not dates:
                add("time", "G", hm(at_min) + note12)
                add("date", ".", f"not in span; {at_date} is the AI's")
            else:
                add(
                    "time",
                    "G",
                    hm(at_min) + note12 + binding_note + (f" on {show_date(dates[0])}" if iso and text.kind == "prose" else ""),
                )
                time_ok = True
        elif timed:
            dates = timed[0][1]
            add("time", "G", hm(at_min) + note12)
            said = res["span_date_text"] if text.kind == "csv" else ", ".join(show_date(d) for d in dates)
            add("date", "R", f"span says {said}; world says {at_date}")
            if len(dates) == 1:
                year, month, day = dates[0]
                year = year or int(at_date[:4])
                out["edits"]["at"] = f"{year:04d}-{month:02d}-{day:02d}T{at_min // 60:02d}:{at_min % 60:02d}"
        else:
            all_dates = [d for f in found for d in f[1]]
            if text.kind == "csv":
                said = ", ".join(show_cands(c) for c, _ in found) + (
                    f" on {res['span_date_text']}" if res.get("span_date_text") else ""
                )
            else:
                said = ", ".join(show_cands(c) for c, _ in found) + (
                    f" on {', '.join(show_date(d) for d in dict.fromkeys(all_dates))}" if iso and all_dates else ""
                )
            add(
                "time",
                "R",
                f"span says {said}; world says {event['at']}" + (table_hint(res, at_min) if text.kind == "csv" else ""),
            )
            if len(found) == 1 and len(found[0][0]) == 1:
                new = next(iter(found[0][0]))
                dates = found[0][1]
                if kind == "clock":
                    out["edits"]["at"] = hm(new)
                else:
                    if len(dates) == 1:
                        year, month, day = dates[0]
                        day_text = f"{year or int(at_date[:4]):04d}-{month:02d}-{day:02d}"
                    else:
                        day_text = at_date
                    out["edits"]["at"] = f"{day_text}T{new // 60:02d}:{new % 60:02d}"
    # people, things, places: only prose names them
    actor_ok = text.kind == "csv" or not event.get("actor")
    if text.kind == "prose" and event.get("actor"):
        actor = event["actor"]
        where = {p: named_at(p, span, aliases) for p in persons}
        in_span = {p for p, hit in where.items() if hit}
        bound_actor, ambiguity = _event_actor_binding(actor_span, actor, persons, aliases)
        if ambiguity:
            add("actor", ".", ambiguity)
        elif bound_actor == actor:
            add("actor", "G", actor)
            actor_ok = True
        elif bound_actor:
            add("actor", "R", f"span actor is {bound_actor}, not {actor}")
            out["edits"]["actor"] = bound_actor
        else:
            add("actor", ".", f"{actor} not named in event span")
        for who in event.get("with", []) or []:
            add("with", "G" if who in in_span else ".", who if who in in_span else f"{who} not named")
        uses = event.get("uses", []) or []
        uses = [uses] if isinstance(uses, str) else list(uses)
        for index, thing in enumerate(uses):
            if named(thing, span, aliases) or code_present(thing, span):
                add("uses", "G", thing)
                continue
            shape = code_shape(thing)
            seen = sorted(set(codes_in(span, shape))) if shape else []
            if seen:
                add("uses", "R", f"span names {', '.join(seen)}, not {thing}")
                if len(seen) == 1:
                    out["edits"]["uses"] = [*uses[:index], seen[0], *uses[index + 1 :]]
            else:
                add("uses", ".", f"{thing} not named")
        if event.get("place"):
            word = named(event["place"], span, aliases) or (
                event["place"] if code_present(event["place"], span) else None
            )
            shape = None if word else code_shape(event["place"])
            seen = sorted(set(codes_in(span, shape))) if shape else []
            if seen:
                add("place", "R", f"span names {', '.join(seen)}, not {event['place']}")
                if len(seen) == 1:
                    out["edits"]["place"] = seen[0]
            else:
                add(
                    "place",
                    "G" if word else ".",
                    (
                        (event["place"] + (f" (as '{word}')" if word != event["place"] else ""))
                        if word
                        else f"{event['place']} not named"
                    ),
                )
    out["sourced"] = time_ok and actor_ok and not any(c == "R" for _, c, _ in out["readings"])
    return out


def read_value(name: str, spec: dict, contracts: dict, texts: dict, cited: dict) -> dict:
    """A number the AI typed into the world (one or more paths), read from its pointer and the declared unit.
    A range in the text makes two text worlds, one at each end; an ambiguous number is never green."""
    out = {
        "name": name,
        "pointer": spec.get("source", ""),
        "readings": [],
        "edits_lo": [],
        "edits_hi": [],
        "range": False,
        "sourced": False,
        "paths": [],
    }
    add = lambda field, colour, note: out["readings"].append((field, colour, note))  # noqa: E731
    paths = spec.get("paths") or ([spec["path"]] if "path" in spec else [])
    if not paths or not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
        raise WorldInputError(f"values.{name} needs paths: a nonempty list of world paths")
    for raw in paths:
        node, path = raw.split(":", 1) if ":" in raw.split(".", 1)[0] else (None, raw)
        parent, key = _select_path(contracts[node], path)
        out["paths"].append((node, path, parent[key]))
    unit = str(spec.get("unit", "1"))
    declared = unit_info(unit) if unit != "1" else (None, 1.0, 0.0)
    if declared is None:
        add("unit", ".", f"declared unit {unit!r} is unreadable; PhysicsGuard unit support is needed")
        return out
    want_dim, want_factor, want_offset = declared
    if want_offset:
        add("unit", ".", f"declared unit {unit!r} has an offset; this source comparison does not convert it")
        return out
    res = resolve(spec.get("source", ""), texts, cited, add)
    if res is None:
        return out
    source_text = (
        res["cell"]
        if res["text"].kind == "csv"
        else (res["quote"] if res.get("quote") and not res.get("quote_missing") else res["span"])
    )
    found = quantities(source_text, res["text"].decimal)
    fitting = [q for q in found if q["dim"] == want_dim and q["factor"] is not None and (q["readable"] or unit == "1")]
    if not found:
        add("value", ".", "span states no number")
        return out
    if not fitting:
        q = found[0]
        if want_dim is not None and all(f["dim"] is None for f in found):
            add(
                "value",
                ".",
                f"span says {', '.join(f['written'] for f in found)} with no unit; the world value is in {unit}",
            )
        elif any(not q["readable"] and q["unit"] for q in found):
            add(
                "unit",
                ".",
                f"unreadable source unit in {', '.join(f['written'] for f in found)}; no conversion guessed",
            )
        elif want_dim is None:
            add(
                "value",
                ".",
                f"span says {', '.join(f['written'] for f in found)}; the world value has no unit declared",
            )
        else:
            add(
                "value",
                "R",
                f"span says {q['written']} ({q['dim']}); the world value is declared in {unit} ({want_dim})",
            )
        return out
    if len(fitting) > 1:
        add(
            "value",
            ".",
            f"span states {len(fitting)} numbers ({', '.join(f['written'] for f in fitting)}); quote the one meant",
        )
        return out
    q = fitting[0]
    conv = lambda v: v * q["factor"] / want_factor  # noqa: E731
    in_unit = "" if want_dim is None or q["factor"] == want_factor else f" {unit}"
    worlds = sorted({fmt(v) for _, _, v in out["paths"]})
    numeric = [float(v) for _, _, v in out["paths"] if isinstance(v, (int, float))]
    close = lambda a, b: abs(a - b) <= 0.01 * abs(b) + 1e-9  # noqa: E731
    exact = lambda x: int(round(x, 6)) if round(x, 6) == int(round(x, 6)) else round(x, 6)  # noqa: E731
    if q["lo"] != q["hi"]:
        lo, hi = conv(q["lo"]), conv(q["hi"])
        said = f"{q['written']}" + (f" = {fmt(lo)}..{fmt(hi)}{in_unit}" if in_unit else "")
        out["range"] = True
        out["edits_lo"] = [(node, path, exact(lo)) for node, path, _ in out["paths"]]
        out["edits_hi"] = [(node, path, exact(hi)) for node, path, _ in out["paths"]]
        if len(numeric) == len(out["paths"]) and all(
            lo - 1e-9 <= v <= hi + 1e-9 or close(v, lo) or close(v, hi) for v in numeric
        ):
            add(
                "value",
                ".",
                f"span says {said}; world says {', '.join(worlds)}, one point of the range (the text's world is checked at both ends)",
            )
        else:
            add("value", "R", f"span says {said}; world says {', '.join(worlds)}, outside the range")
        return out
    if q["alts"]:
        cands = [conv(a) for a in q["alts"]]
        how = " or ".join(fmt(c) + in_unit for c in cands)
        hint = f"declare decimal: {{{res['label']}: ','}} or '.' in the sidecar"
        if len(numeric) == len(out["paths"]) and any(all(close(v, c) for v in numeric) for c in cands):
            add("value", ".", f"span says {q['written']}, which is {how}; world says {', '.join(worlds)} ({hint})")
        else:
            add("value", "R", f"span says {q['written']}, which is {how}; world says {', '.join(worlds)} ({hint})")
        return out
    converted = conv(q["lo"])
    said = q["written"] + (f" = {fmt(converted)}{in_unit}" if in_unit else "")
    bad = sorted(
        {fmt(v) for _, _, v in out["paths"] if not isinstance(v, (int, float)) or not close(float(v), converted)}
    )
    if bad:
        add("value", "R", f"span says {said}; world says {', '.join(bad)}")
        out["edits_lo"] = out["edits_hi"] = [(node, path, exact(converted)) for node, path, _ in out["paths"]]
    else:
        add("value", "G", f"span says {said}; world says {', '.join(worlds)}")
        out["sourced"] = True
    return out


def code_present(name, span):
    shape = code_shape(name)
    if not shape:
        return False
    normal = str(name).replace("_", "").replace(" ", "").replace("-", "").lstrip("vV").lower()
    return any(value.lower().lstrip("vV") == normal for value in codes_in(span, shape))


def read_contract_values(contract, raw, texts, cited, context):
    contracts = {None: raw}
    current = None
    if context is not None and context.node_contracts:
        contracts.update({key: value.to_dict() for key, value in context.node_contracts.items()})
        current = next((key for key, value in context.node_contracts.items() if value is contract), None)
    values = []
    for name, spec in contract.source_config.get("values", {}).items():
        if not isinstance(spec, dict):
            raise WorldInputError(f"values.{name} must be a mapping")
        paths = spec.get("paths") or ([spec["path"]] if "path" in spec else [])
        if not paths or not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
            raise WorldInputError(f"values.{name} needs paths: a nonempty list of world paths")
        selected = [path for path in paths if ":" not in path.split(".", 1)[0] or path.split(":", 1)[0] == current]
        if selected:
            values.append(read_value(name, {**spec, "paths": selected}, contracts, texts, cited))
    return values


def source_citations(texts, context=None):
    """A shared document paragraph is cited once across the actual mesh, by file identity."""
    cited = {}
    if context is None or not context.node_contracts:
        return cited
    paths = {}
    for label, text in texts.items():
        paths.setdefault(text.path.resolve(), set()).add(label)
    for other in context.node_contracts.values():
        config = other.source_config
        pointers = [event.get('source', '') for event in other.inputs.get('events', [])]
        pointers.extend(value.get('source', '') for value in config.get('values', {}).values()
                        if isinstance(value, dict))
        for pointer in pointers:
            match = POINTER.fullmatch(str(pointer))
            if match is None or match['label'] not in config.get('texts', {}):
                continue
            path = (Path(other.source_base_dir) / config['texts'][match['label']]).resolve()
            number = int(match['para'] or match['row'])
            for label in paths.get(path, ()):
                if 1 <= number <= texts[label].units:
                    cited.setdefault(label, set()).add(number)
    return cited


def attach_readings(contract, report, *, context=None):
    """Leave an unsourced model untouched; source-enabled models expose every reading."""
    if not contract.source_config:
        return report
    texts = load_texts(contract.source_config, contract.source_base_dir)
    cited = source_citations(texts, context)
    raw = contract.to_dict()
    readings = [
        read_event(event, texts, contract.source_config.get("aliases", {}), world_names(raw), cited)
        for event in contract.inputs.get("events", [])
    ]
    values = read_contract_values(contract, raw, texts, cited, context)
    gaps = list(report.gaps)
    for reading in [*readings, *values]:
        for field, colour, note in reading["readings"]:
            if colour != "R":
                continue
            code = {
                "span": "SOURCE_SPAN_MISSING",
                "quote": "SOURCE_QUOTE_NOT_IN_TEXT",
                "time": "SOURCE_TIME_DISAGREES",
                "date": "SOURCE_TIME_DISAGREES",
                "actor": "SOURCE_ACTOR_DISAGREES",
            }.get(field, "SOURCE_VALUE_DISAGREES")
            gaps.append(
                {
                    "code": code,
                    "status": "FAIL",
                    "event_id": reading.get("event"),
                    "source": reading["pointer"],
                    "message": note,
                }
            )
    limits = list(report.scope_limits)
    for label, text in texts.items():
        for number in range(1, text.units + 1):
            if number not in cited.get(label, set()):
                limits.append(
                    f'TEXT_UNCITED {label} {"r" if text.kind == "csv" else "p"}{number}: {text.unit_text(number)}'
                )
    checked = {
        **report.checked,
        "source_readings": readings,
        "ai_world_status": report.status.value,
        "source_values": values,
        "source_digests": input_digests([text.path for text in texts.values()], contract.source_base_dir),
    }
    updated = replace(
        report,
        status=GuardStatus.FAIL if gaps != report.gaps else report.status,
        checked=checked,
        gaps=gaps,
        scope_limits=limits,
    )
    return attach_text_worlds(contract, updated, readings, values, texts, cited, context=context, native_report=report)


def support(contract: dict, asserts: list) -> list[tuple[set, set | None]]:
    """For each claim row, every event and scenario value it can rest on (a superset, on purpose):
    `holds X at T` reads the state at T, so every event at or before T; `A before B` reads A and B; `variable v`
    reads the event times (t_<event>) and the scenario values its equations name, followed through other variables;
    any other row reads the whole replay and every sourced value (None). Removing one event at a time is not used:
    WorldGuard blocks the effects of an event whose precondition fails but not of the events after it, so a row can
    still pass without an event it needs."""
    events = [e for e in contract.get("inputs", {}).get("events", []) if "at" in e]
    causal = contract.get("inputs", {}).get("causal_model", {}) or {}
    equations = causal.get("equations", {}) or {}
    result = []
    for a in asserts:
        if "holds" in a and "at" in a:
            limit = time_key(a["at"])
            result.append(({e["event_id"] for e in events if time_key(e["at"]) <= limit}, set()))
        elif "event" in a and "before" in a:
            result.append(({a["event"], a["before"]}, set()))
        elif "variable" in a:
            todo, seen, used, inputs = [a["variable"]], set(), set(), set()
            while todo:
                name = todo.pop()
                if name in seen:
                    continue
                seen.add(name)
                for token in re.findall(r"[A-Za-z_]\w*", str(equations.get(name, ""))):
                    if token.startswith("t_"):
                        used.add(token[2:])
                    elif token in equations:
                        todo.append(token)
                    else:
                        inputs.add(token)
            result.append((used, inputs))
        else:
            result.append(({e["event_id"] for e in events}, None))
    return result


def scenario_var(path: str) -> str | None:
    match = re.match(r"^inputs\.causal_model\.(?:scenarios|holdout_scenarios)\.[^.]+\.([A-Za-z_]\w*)$", path)
    return match[1] if match else None


def _scenario_names(contract):
    causal = contract.get("inputs", {}).get("causal_model", {}) or {}
    return set(map(str, causal.get('exogenous', []) or [])) | {
        str(name)
        for group in ("scenarios", "holdout_scenarios")
        for values in causal.get(group, {}).values()
        for name in values
    }


def _bundle_identity(sources):
    import json

    payload = json.dumps(sources, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _row_status(report, index):
    rows = report.claim_binding.get("assertions", [])
    return next((row["status"] for row in rows if row["index"] == index), "GAP")


def _source_evidence(contract, context=None):
    raw = contract.to_dict()
    texts = load_texts(contract.source_config, contract.source_base_dir)
    cited = source_citations(texts, context)
    readings = [
        read_event(event, texts, contract.source_config.get("aliases", {}), world_names(raw), cited)
        for event in contract.inputs.get("events", [])
    ]
    values = read_contract_values(contract, raw, texts, cited, context)
    return raw, texts, cited, readings, values


def attach_text_worlds(contract, report, readings, values, texts, cited, *, context=None, native_report=None):
    """Replay explicit text edits through the existing world owner; qualify only that finite world."""
    from .qualification import qualify_guard_contract

    raw = contract.to_dict()
    ends = ["lo", "hi"] if any(value["range"] for value in values) else ["lo"]
    worlds, text_reports = [], []
    for end in ends:
        edits = {
            f"inputs.events[{reading['event']}].{field}": value
            for reading in readings
            for field, value in reading["edits"].items()
        }
        edits.update({path: value for row in values for _, path, value in row[f"edits_{end}"]})
        if edits:
            changed = apply_variant(raw, {"id": "as_the_text_says", "set": edits})
            text_report = qualify_guard_contract(changed, context=context)
        else:
            text_report = native_report or report
        text_reports.append(text_report)
        worlds.append(
            {
                "end": end,
                "status": text_report.status.value,
                "edits": [{"path": path, "value": value} for path, value in sorted(edits.items())],
                "gaps": text_report.gaps,
            }
        )
    statuses = []
    sources = report.checked["source_digests"]
    for row in report.claim_binding.get("assertions", []):
        assertion, index = row["assertion"], row["index"]
        target = assertion.get("node")
        target_contract = (
            context.node_contracts.get(target) if target and context and context.node_contracts else contract
        )
        evidence = (
            (raw, texts, cited, readings, values)
            if target_contract is contract
            else _source_evidence(target_contract, context) if target_contract is not None else None
        )
        problems = []
        weak = []
        if row["status"] != "PASS" or any(_row_status(result, index) != "PASS" for result in text_reports):
            problems.append("AI world or text world does not pass this assertion")
        if evidence is None:
            weak.append("target model has no source evidence")
        else:
            target_raw, target_texts, target_cited, target_readings, target_values = evidence
            rests, inputs = support(target_raw, [{key: value for key, value in assertion.items() if key != "node"}])[0]
            failures = [
                gap
                for result in [report, *text_reports]
                for gap in result.gaps
                if gap.get("status") == "FAIL"
                and (gap.get("event_id") or (gap.get("counterexample") or {}).get("event_id")) in rests
            ]
            problems.extend(f"supporting event cannot happen: {gap['code']}" for gap in failures)
            used_readings = [reading for reading in target_readings if reading["event"] in rests]
            by_event = {reading["event"]: reading for reading in used_readings}
            relevant_values = [
                value
                for value in target_values
                if inputs is None or any(scenario_var(path) in inputs for _, path, _ in value["paths"])
            ]
            for event in sorted(rests):
                reading = by_event.get(event)
                if reading and any(colour == "R" for _, colour, _ in reading["readings"]):
                    problems.append(f"text disagrees on {event}")
                elif not reading or not reading["sourced"]:
                    weak.append(f"{event} not sourced")
            for value in relevant_values:
                if any(colour == "R" for _, colour, _ in value["readings"]):
                    problems.append(f"text disagrees on value {value['name']}")
                elif not value["sourced"]:
                    weak.append(f"value {value['name']} not sourced")
            supplied = {scenario_var(path) for value in relevant_values for _, path, _ in value["paths"]}
            weak.extend(
                f"value {name} has no pointer"
                for name in sorted((inputs or set()) & _scenario_names(target_raw) - supplied)
            )
            event_minutes = [
                at_parts(event["at"])[2]
                for event in target_raw.get("inputs", {}).get("events", [])
                if event.get("event_id") in rests and "at" in event
            ]
            latest = max([minute for minute in event_minutes if minute is not None] or [0])
            labels = {
                match["label"] for reading in target_readings if (match := POINTER.match(str(reading["pointer"])))
            }
            aliases = target_contract.source_config.get("aliases", {})
            names = world_names(target_raw)
            for label in sorted(labels):
                text = target_texts[label]
                for number in range(1, text.units + 1):
                    if number in target_cited.get(label, set()):
                        continue
                    span = text.unit_text(number)
                    named_person = any(named(name, span, aliases) for group in names for name in group)
                    times = text.unit_times(number)
                    if named_person and (not times or min(times) <= latest):
                        weak.append(f'uncited text in its window: {label} {"r" if text.kind == "csv" else "p"}{number}')
        colour = "red" if problems else "grey" if weak else "green"
        reason = (
            "; ".join(problems + weak) if problems or weak else "AI world and text world pass; relevant inputs sourced"
        )
        if colour == "grey":
            reason = "passes on AI transcription only; " + reason
        row_sources = (input_digests([text.path for text in evidence[1].values()], contract.source_base_dir)
                       if evidence is not None else sources)
        status = {
            "id": f"{contract.claim.claim_id or contract.contract_id}:{index}",
            "colour": colour,
            "reason": reason,
            "source_digest": _bundle_identity(row_sources),
            "sources": row_sources,
        }
        statuses.append(status)
    checked = {
        **report.checked,
        "ai_world_status": report.checked.get("ai_world_status", report.status.value),
        "text_worlds": worlds,
        "source_statuses": statuses,
    }
    binding = deepcopy(report.claim_binding)
    for row, status in zip(binding.get("assertions", []), statuses):
        row["source_status"] = status
    gaps = list(report.gaps)
    for result in text_reports:
        for gap in result.gaps:
            if gap not in report.gaps and {**gap, "world": "text"} not in gaps:
                gaps.append({**gap, "world": "text"})
    return replace(
        report,
        checked=checked,
        gaps=gaps,
        claim_binding=binding,
        status=aggregate_statuses([report.status, *[result.status for result in text_reports]]),
    )
