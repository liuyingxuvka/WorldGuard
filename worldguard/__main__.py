"""Run the WorldGuard CLI through ``python -m worldguard``."""

from __future__ import annotations

import sys
import json

from .cli import main


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        # Keep the module entry point's terminal contract identical to the
        # portable helper: a domain failure is a single JSON error envelope,
        # not an implementation traceback on stderr.  This is an error
        # projection, not a retry or alternate execution path.
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
