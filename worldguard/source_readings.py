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
    times_in,
    sentences,
    time_mentions,
    date_mentions,
    date_matches,
    show_date,
    show_cands,
    hm,
    strip_times_dates,
)
from .status import GuardStatus

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
    if any(value not in {".", ","} for value in config.get("decimal", {}).values()):
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
    para_dates = list(dict.fromkeys(date_mentions(span)))
    head_dates = list(dict.fromkeys(date_mentions(text.heads[res["n"] - 1])))
    out = []
    for cands, index in time_mentions(span, text.conv24):
        own = list(dict.fromkeys(date_mentions(sents[index]))) if index < len(sents) else []
        out.append(
            (cands, own or (para_dates if len(para_dates) == 1 else []) or (head_dates if len(head_dates) == 1 else []))
        )
    return out


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
    found = mentions_with_dates(res)
    time_ok = False
    if "at" not in event:
        add("time", ".", "event has no time")
    elif at_min is None:
        add("time", ".", f"world clock is {kind}s; nothing to compare")
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
                    hm(at_min) + note12 + (f" on {show_date(dates[0])}" if iso and text.kind == "prose" else ""),
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
            if len(found) == 1:
                new = min(found[0][0], key=lambda c: abs(c - at_min))
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
        participants = {actor, *(event.get("with", []) or [])}
        where = {p: named_at(p, span, aliases) for p in persons}
        in_span = {p for p, hit in where.items() if hit}
        others = sorted(in_span - participants)
        if actor in in_span:
            first = [w for w in event.get("with", []) or [] if w in in_span and where[w][1] < where[actor][1]]
            if first:
                add("actor", ".", f"{', '.join(first)} named before {actor}: who acts is not read")
            else:
                add("actor", "G", actor)
                actor_ok = True
        elif others:
            add("actor", "R", f"span names {', '.join(others)}, not {actor}")
            if len(others) == 1:
                out["edits"]["actor"] = others[0]
        else:
            add("actor", ".", f"{actor} not named in span (pronoun?)")
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


def code_present(name, span):
    shape = code_shape(name)
    if not shape:
        return False
    normal = str(name).replace("_", "").replace(" ", "").replace("-", "").lstrip("vV").lower()
    return any(value.lower().lstrip("vV") == normal for value in codes_in(span, shape))


def attach_readings(contract, report, *, context=None):
    """Leave an unsourced model untouched; source-enabled models expose every reading."""
    if not contract.source_config:
        return report
    texts = load_texts(contract.source_config, contract.source_base_dir)
    cited = {}
    raw = contract.to_dict()
    readings = [
        read_event(event, texts, contract.source_config.get("aliases", {}), world_names(raw), cited)
        for event in contract.inputs.get("events", [])
    ]
    gaps = list(report.gaps)
    for reading in readings:
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
                    "event_id": reading["event"],
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
        "source_digests": input_digests([text.path for text in texts.values()], contract.source_base_dir),
    }
    return replace(
        report,
        status=GuardStatus.FAIL if gaps != report.gaps else report.status,
        checked=checked,
        gaps=gaps,
        scope_limits=limits,
    )
