"""Emit current target-owned WorldGuard execution-depth evidence as JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from worldguard.execution_depth import build_native_depth_evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--expected-status")
    parser.add_argument("--expected-blocker-code")
    args = parser.parse_args()
    try:
        evidence = build_native_depth_evidence(
            args.input,
            expected_status=args.expected_status,
            expected_blocker_code=args.expected_blocker_code,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps({"ok": True, "evidence": evidence}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
