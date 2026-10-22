"""The single parser and comparison scale for declared event times."""
from __future__ import annotations

import math
import re
from datetime import date, datetime, time, timezone
from typing import Any, Iterable

_LABEL = re.compile(r"^([A-Za-z_]+)(-?\d+(?:\.\d+)?)$")
_CLOCK = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?$")
_FORMATS = "use a number, a label such as t<number>, an ISO date-time, or HH:MM[:SS]"


def _parts(value: Any) -> tuple[str, str, float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isfinite(value):
            return "number", "", float(value)
    elif isinstance(value, (date, datetime)):
        stamp = value if isinstance(value, datetime) else datetime.combine(value, time())
        aware = stamp.utcoffset() is not None
        return "ISO date-time", "aware" if aware else "naive", (stamp if aware else stamp.replace(tzinfo=timezone.utc)).timestamp()
    elif isinstance(value, str):
        text = value.strip()
        match = _LABEL.fullmatch(text)
        if match:
            return "label", match[1], float(match[2])
        match = _CLOCK.fullmatch(text)
        if match:
            return "clock", "", int(match[1]) * 3600 + int(match[2]) * 60 + int(match[3] or 0)
        try:
            stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            pass
        else:
            aware = stamp.utcoffset() is not None
            return "ISO date-time", "aware" if aware else "naive", (stamp if aware else stamp.replace(tzinfo=timezone.utc)).timestamp()
    raise ValueError(f"{value!r} is not a time; {_FORMATS}")


def time_key(value: Any) -> float:
    """Return a numeric ordering key; callers validate one contract's kinds first."""
    return _parts(value)[2]


def time_kind(value: Any) -> str:
    return _parts(value)[0]


def validate_times(values: Iterable[tuple[str, Any]]) -> None:
    """Require one format, label prefix, and ISO timezone convention per contract."""
    first = None
    for location, value in values:
        try:
            kind, qualifier, _ = _parts(value)
        except ValueError as exc:
            raise ValueError(f"{location}: at {exc}") from exc
        if first is None:
            first = (location, value, kind, qualifier)
        elif (kind, qualifier) != first[2:]:
            hint = ('; unquoted H:MM in YAML is read as a number; quote clock times, e.g. at: "9:40"'
                    if {kind, first[2]} == {"number", "clock"} else "")
            raise ValueError(
                f"event times mix kinds, label prefixes, or ISO timezone conventions: "
                f"{first[0]} {first[1]!r} ({first[2]} {first[3]}) and "
                f"{location} {value!r} ({kind} {qualifier}); {_FORMATS}{hint}"
            )
