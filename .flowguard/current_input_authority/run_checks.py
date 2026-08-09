"""Direct-current runner for the current-input model owner.

The runner names the owner entry point explicitly so FlowGuard can bind the
native evidence path to a concrete callable instead of treating a dynamic
``runpy`` launch as an opaque provider gap.
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_semantic_rollout_checks import main as run_semantic_rollout_checks  # noqa: E402


def main() -> int:
    return int(run_semantic_rollout_checks())


if __name__ == "__main__":
    raise SystemExit(main())
