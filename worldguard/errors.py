"""The one exception type for invalid input.

`WorldInputError` means the person's input is wrong: a world, a tree, an observation file, a record field or a command
argument. Reading an input file that cannot be read or decoded raises it too (`io.py` names the file). The command line
turns exactly this type into `WORLDGUARD_INPUT_INVALID`, exit 2. Any other exception, including an `OSError`, a
`UnicodeError` or a plain `ValueError` raised inside WorldGuard after the files were read, is a fault of the tool and
reaches the caller with its traceback; it is never reported as an input error or turned into a result.
"""

from __future__ import annotations


class WorldInputError(ValueError):
    """The input is invalid; the message says which field and why."""


__all__ = ["WorldInputError"]
