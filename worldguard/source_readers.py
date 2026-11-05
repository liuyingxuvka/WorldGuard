"""Small source readers; ambiguous language stays explicit and units belong to PhysicsGuard."""

from __future__ import annotations

import importlib.util
import re
import unicodedata
from typing import NamedTuple

_TYPO = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "′": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "″": '"',
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "−": "-",
        "­": None,
    }
)


def norm(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(text)).translate(_TYPO).split())


# ---------- times ----------

HOUR_WORDS = {w: n for n, w in enumerate("one two three four five six seven eight nine ten eleven twelve".split(), 1)}
SMALL = {
    w: n
    for n, w in enumerate(
        (
            "zero one two three four five six seven eight nine ten eleven twelve thirteen "
            "fourteen fifteen sixteen seventeen eighteen nineteen"
        ).split()
    )
}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_NUMWORD = (
    r"(?:(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?"
    r"|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen"
    r"|seventeen|eighteen|nineteen)"
)
_HOUR = r"(?:1[0-2]|0?[1-9]|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
CLOCK = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b(?!\s*[ap]\.?m\b)", re.I)
AMPM = re.compile(r"\b(1[0-2]|0?[1-9])(?:[:.]([0-5]\d))?\s*([ap])\.?m\.?(?![a-z])", re.I)
WORDED = re.compile(
    rf"\b(?:a\s+)?(quarter|half|\d{{1,2}}|{_NUMWORD})(?:\s+minutes?)?\s+(past|after|to|before)\s+({_HOUR})\b"
    r"(?!\s*(?:hours?|hrs?|minutes?|mins?|days?|weeks?|months?|years?|people|persons|times)\b)",
    re.I,
)
OCLOCK = re.compile(rf"\b({_HOUR})\s*o['’]?\s?clock\b", re.I)
CELL_TIME = re.compile(r"^\s*([01]?\d|2[0-3])[.:h]([0-5]\d)\s*$")
PM_WORDS = re.compile(r"\b(afternoon|evening|tonight)\b", re.I)
AM_WORDS = re.compile(r"\b(morning)\b", re.I)
NIGHT = re.compile(r"\bnight\b", re.I)


def word_number(token: str) -> int | None:
    token = token.lower().replace("-", " ")
    if token.isdigit():
        return int(token)
    parts = token.split()
    if len(parts) == 1:
        return SMALL.get(parts[0], TENS.get(parts[0]))
    if len(parts) == 2 and parts[0] in TENS and parts[1] in SMALL and SMALL[parts[1]] < 10:
        return TENS[parts[0]] + SMALL[parts[1]]
    return None


ABBREV = re.compile(
    r"(?:\b(?:Dr|Mr|Mrs|Ms|St|Mt|No|Nr|ca|approx|vs|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"|\b[ap]\.m|\be\.g|\bi\.e)\.$",
    re.I,
)


def sentences(text: str) -> list[str]:
    """Sentences of a paragraph; a full stop after an abbreviation (Oct., Dr., a.m.) does not end one."""
    out: list[str] = []
    for part in re.split(r"(?<=[.!?;])\s+(?=[A-Z0-9\"'])", text):
        if out and ABBREV.search(out[-1]):
            out[-1] += " " + part
        elif part:
            out.append(part)
    return out


def uses_24h(full_text: str) -> bool:
    """The file writes clock times the 24-hour way (an hour of 13 or more, or a leading zero)."""
    return any(int(h) >= 13 or (len(h) == 2 and h.startswith("0")) for h, _m in CLOCK.findall(full_text))


def _twelve(hour: int, minute: int, sentence: str) -> set[int]:
    """Candidates for a 12-hour reading with no a.m./p.m.: one when a day-part word in the sentence says which half."""
    base = (hour % 12) * 60 + minute
    if PM_WORDS.search(sentence) or (NIGHT.search(sentence) and 6 <= hour <= 11):
        return {base + 720}
    if AM_WORDS.search(sentence) or (NIGHT.search(sentence) and (hour == 12 or hour < 6)):
        return {base}
    return {base, base + 720}


def time_mentions(text: str, conv24: bool = True) -> list[tuple[set[int], int]]:
    """Every time stated in the text: (candidate minutes after midnight, sentence index). A 12-hour mention without
    a.m./p.m. or a day-part word has two candidates."""
    found = []
    for index, sentence in enumerate(sentences(text)):
        for match in CLOCK.finditer(sentence):
            hour, minute = int(match[1]), int(match[2])
            if 1 <= hour <= 12 and (
                PM_WORDS.search(sentence) or AM_WORDS.search(sentence) or NIGHT.search(sentence) or not conv24
            ):
                found.append((_twelve(hour, minute, sentence), index))
            else:
                found.append(({hour * 60 + minute}, index))
        for h, m, ap in AMPM.findall(sentence):
            found.append(({(int(h) % 12 + (12 if ap.lower() == "p" else 0)) * 60 + int(m or 0)}, index))
        for amount, relation, hour_word in WORDED.findall(sentence):
            hour = int(hour_word) if hour_word.isdigit() else HOUR_WORDS[hour_word.lower()]
            minutes = {"quarter": 15, "half": 30}.get(amount.lower()) or word_number(amount)
            if (
                minutes is None
                or not 0 < minutes < 60
                or (amount.lower() == "half" and relation.lower() in {"to", "before"})
            ):
                continue
            if relation.lower() in {"to", "before"}:
                hour, minutes = (hour - 1) or 12, 60 - minutes
            found.append((_twelve(hour, minutes, sentence), index))
        for hour_word in OCLOCK.findall(sentence):
            found.append(
                (_twelve(int(hour_word) if hour_word.isdigit() else HOUR_WORDS[hour_word.lower()], 0, sentence), index)
            )
        if re.search(r"\bnoon\b", sentence, re.I):
            found.append(({720}, index))
        if re.search(r"\bmidnight\b", sentence, re.I):
            found.append(({0}, index))
    return found


def times_in(text: str) -> list[int]:
    """Flat list of times (used for uncited text); 12-hour mentions give both candidates."""
    return sorted({c for cands, _ in time_mentions(text) for c in cands})


def hm(minutes: int) -> str:
    return f"{minutes // 60}:{minutes % 60:02d}"


def show_cands(cands: set[int]) -> str:
    return " or ".join(hm(c) for c in sorted(cands))


# ---------- dates ----------

MONTHS = {
    m: i
    for i, m in enumerate(
        "January February March April May June July August September October November December".split(), 1
    )
}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})
MONTHS["Sept"] = 9
_MON = "|".join(sorted(MONTHS, key=len, reverse=True))
D_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
D_DMY = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?(?:\s+of)?\s+({_MON})\.?(?:,?\s+(\d{{4}}))?\b")
D_MDY = re.compile(rf"\b({_MON})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(\d{{4}}))?")
D_DOT = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")


def date_mentions(text: str) -> list[tuple[int | None, int, int]]:
    """Dates stated in the text as (year or None, month, day). Month names are matched capitalised only, so the verb
    'may' is no date; D/M/Y with slashes is not read (day and month order unknown)."""
    found = []
    taken = []
    for pattern, order in ((D_ISO, "ymd"), (D_DOT, "dmy"), (D_DMY, "dMy"), (D_MDY, "Mdy")):
        for match in pattern.finditer(text):
            if any(a < match.end() and match.start() < b for a, b in taken):
                continue
            g = match.groups()
            if order == "ymd":
                year, month, day = int(g[0]), int(g[1]), int(g[2])
            elif order == "dmy":
                day, month, year = int(g[0]), int(g[1]), int(g[2])
            elif order == "dMy":
                day, month, year = int(g[0]), MONTHS[g[1]], int(g[2]) if g[2] else None
            else:
                month, day, year = MONTHS[g[0]], int(g[1]), int(g[2]) if g[2] else None
            if 1 <= month <= 12 and 1 <= day <= 31:
                found.append((year, month, day))
                taken.append((match.start(), match.end()))
    return found


def show_date(date) -> str:
    year, month, day = date
    name = [m for m, i in MONTHS.items() if i == month and len(m) > 3 and m != "Sept"][0]
    return f"{day} {name}" + (f" {year}" if year else "")


def date_matches(date, iso: str) -> bool:
    year, month, day = date
    y, m, d = (int(x) for x in iso.split("-"))
    return (month, day) == (m, d) and (year is None or year == y)


def strip_times_dates(text: str) -> str:
    for pattern in (D_ISO, D_DOT, D_DMY, D_MDY, AMPM, CLOCK, WORDED, OCLOCK):
        text = pattern.sub(" ", text)
    return re.sub(r"\b(noon|midnight)\b", " ", text, flags=re.I)


class UnitInfo(NamedTuple):
    dim: tuple[int, ...]
    factor: float
    offset: float


def unit_info(label: str, unit_reader=None) -> UnitInfo | None:
    """Ask the single unit owner. An absent owner or unreadable label is not a conversion."""
    if unit_reader is None:
        if importlib.util.find_spec("physicsguard") is None:
            return None
        from physicsguard.core.units import read_unit

        unit_reader = read_unit
    read = unit_reader(label)
    return UnitInfo(tuple(read.exponents), read.factor, read.offset) if read else None


THIN = "\u2009\u202f\u00a0'"
NUMBER = re.compile(r"(?<![\w.,])\d+(?:[\u2009\u202f\u00a0'.,]\d+)*(?![\w])")
WORDNUM = re.compile(rf"\b({_NUMWORD})\b", re.I)
_N = rf"(?:a|an|one|{_NUMWORD}|\d+)"
DURATIONS = (
    (re.compile(rf"\b(?:({_N})\s+)?quarters?\s+of\s+an\s+hour\b", re.I), lambda n: 0.25 * n),
    (re.compile(rf"\b({_N})\s+hours?\s+and\s+a\s+half\b", re.I), lambda n: n + 0.5),
    (re.compile(rf"\b({_N})\s+and\s+a\s+half\s+hours\b", re.I), lambda n: n + 0.5),
    (re.compile(r"\b()half\s+an\s+hour\b", re.I), lambda n: 0.5),
    (re.compile(r"\b()an\s+hour\b", re.I), lambda n: 1.0),
)
RANGE_SEP = re.compile(r"^\s*(?:\u2013|\u2014|-|to|until)\s*$", re.I)
COMPACT_DURATION = re.compile(r"(?<!\w)(\d+(?:\.\d+)?)h\s*(\d+(?:\.\d+)?)min(?!\w)", re.I)
_UNIT_PART = re.compile(r"\s*(?:[A-Za-z°º%]+(?:\^?[-+]?\d+)?|[/*·⋅])")


def _count(word: str | None) -> float:
    return 1.0 if not word or word.lower() in {"a", "an", "one"} else float(word_number(word))


def parse_number(token: str, mark: str | None) -> list[float]:
    """Read digit grouping, retaining both interpretations of an undeclared three-digit suffix."""
    groups = re.split(r"[^\d]", token)
    marks = [c for c in token if c in ".,"]
    if not marks:
        return [float("".join(groups))]
    last = marks[-1]
    if mark and last != mark or len(set(marks)) == 1 and len(marks) > 1:
        return [float("".join(groups))]
    head, frac = token.rsplit(last, 1)
    decimal = float(re.sub(r"[^\d]", "", head) + "." + frac)
    if mark or len(set(marks)) == 2 or len(frac) != 3:
        return [decimal]
    return [float(re.sub(r"[^\d]", "", head) + frac), decimal]


def decimal_evidence(text: str) -> str | None:
    """One unambiguous file-level decimal convention, or no inference when conventions conflict."""
    seen = set()
    for token in NUMBER.findall(strip_times_dates(text)):
        marks = [c for c in token if c in ".,"]
        if len(marks) == 1 and len(token.rsplit(marks[0], 1)[1]) != 3:
            seen.add(marks[0])
        elif len(set(marks)) == 2:
            seen.add(marks[-1])
    return next(iter(seen)) if len(seen) == 1 else None


def _unit_after(text: str, unit_reader):
    """Find the longest leading spelling accepted by the owner, retaining an unreadable first token."""
    position, candidates = 0, []
    for _ in range(7):
        match = _UNIT_PART.match(text, position)
        if match is None:
            break
        if match[0].strip().lower() in {"and", "to", "until"}:
            break
        position = match.end()
        candidates.append((text[:position], unit_info(text[:position].strip(), unit_reader)))
    readable = [(label, info) for label, info in candidates if info is not None]
    if readable:
        return readable[-1]
    return (candidates[0][0], None) if candidates else ("", None)


def quantities(text: str, mark: str | None = None, *, unit_reader=None) -> list[dict]:
    """Read finite quantities, ranges and durations. Factors/exponents come only from the supplied or installed PG.

    Each row retains the source spelling, a unit label and its readability. A unit with no owner stays unreadable;
    no factor is guessed. Bare numbers have no dimension. Plain ASCII spaces never join digit groups.
    """
    text = strip_times_dates(unicodedata.normalize("NFC", text))
    tokens = []
    hour, minute, second = (unit_info(label, unit_reader) for label in ("h", "min", "s"))
    for pattern, value in DURATIONS:
        for match in pattern.finditer(text):
            count = value(_count(match[1]))
            tokens.append(
                {
                    "start": match.start(),
                    "end": match.end(),
                    "lo": count,
                    "hi": count,
                    "alts": None,
                    "written": match[0],
                    "dim": hour.dim if hour else None,
                    "factor": hour.factor if hour else None,
                    "unit": "h",
                    "readable": hour is not None,
                }
            )
        text = pattern.sub(lambda m: " " * len(m[0]), text)
    for match in COMPACT_DURATION.finditer(text):
        readable = hour is not None and minute is not None and second is not None
        total = float(match[1]) * hour.factor + float(match[2]) * minute.factor if readable else None
        tokens.append(
            {
                "start": match.start(),
                "end": match.end(),
                "lo": total,
                "hi": total,
                "alts": None,
                "written": match[0],
                "dim": second.dim if readable else None,
                "factor": second.factor if readable else None,
                "unit": "s",
                "readable": readable,
            }
        )
    text = COMPACT_DURATION.sub(lambda m: " " * len(m[0]), text)
    raw = [(m.start(), m.end(), parse_number(m[0], mark), m[0]) for m in NUMBER.finditer(text)]
    raw += [(m.start(), m.end(), [float(word_number(m[1]))], m[0]) for m in WORDNUM.finditer(text)]
    for start, end, cands, written in raw:
        suffix, info = _unit_after(text[end:], unit_reader)
        tokens.append(
            {
                "start": start,
                "end": end + len(suffix),
                "lo": cands[0],
                "hi": cands[0],
                "alts": cands if len(cands) > 1 else None,
                "written": (written + suffix).strip(),
                "dim": info.dim if info else None,
                "factor": info.factor if info else 1.0,
                "unit": suffix.strip(),
                "readable": info is not None or not suffix,
            }
        )
    tokens.sort(key=lambda t: t["start"])
    merged = []
    for tok in tokens:
        prev = merged[-1] if merged else None
        gap = text[prev["end"] : tok["start"]] if prev else ""
        range_gap = RANGE_SEP.fullmatch(gap) or (
            re.fullmatch(r"\s*and\s*", gap) and re.search(r"between\s*$", text[: prev["start"]], re.I)
        )
        if (
            prev
            and not prev["alts"]
            and not tok["alts"]
            and prev["lo"] == prev["hi"]
            and range_gap
            and prev["dim"] in (None, tok["dim"])
        ):
            factor = prev["factor"] if prev["dim"] else tok["factor"]
            if prev["lo"] * factor < tok["lo"] * tok["factor"]:
                merged[-1] = {
                    **tok,
                    "start": prev["start"],
                    "lo": prev["lo"] * factor,
                    "hi": tok["lo"] * tok["factor"],
                    "written": text[prev["start"] : tok["end"]].strip(),
                    "factor": 1.0,
                }
                continue
        if (
            prev
            and second
            and prev["dim"] == tok["dim"] == second.dim
            and prev["readable"]
            and tok["readable"]
            and prev["lo"] == prev["hi"]
            and not tok["alts"]
            and re.fullmatch(r"\s*,?\s*(?:and\s*)?", gap)
            and prev["lo"] * prev["factor"] > tok["lo"] * tok["factor"]
        ):
            total = prev["lo"] * prev["factor"] + tok["lo"] * tok["factor"]
            merged[-1] = {
                **tok,
                "start": prev["start"],
                "lo": total,
                "hi": total,
                "written": text[prev["start"] : tok["end"]].strip(),
                "factor": 1.0,
            }
        else:
            merged.append(tok)
    return merged


def fmt(x: float) -> str:
    return f"{x:.4f}".rstrip("0").rstrip(".") if x != int(x) else str(int(x))
