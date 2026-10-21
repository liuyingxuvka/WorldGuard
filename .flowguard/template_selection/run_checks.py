"""Run the template-selection model and replay its inputs against worldguard.template_packs."""

from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from worldguard_template_pack_builder import native_conformance, review_template_pack_builder  # noqa: E402

IMPLEMENTED_BY = {
    "SelectTemplatePack": "worldguard/template_packs.py:TemplatePackRegistry.select",
    "ComposeTemplatePack": "worldguard/template_packs.py:compose_template_packs",
    "ValidateTemplateInstance": "worldguard/template_packs.py:run_native_template_validators",
}
TESTED_BY = {
    "ambiguity_never_constructs": ["tests/test_template_packs.py:test_many_matching_candidates_are_visible_and_never_ranked"],
    "no_match_never_constructs": ["tests/test_template_packs.py:test_no_candidate_blocks_instead_of_activating_the_shared_scaffold"],
    "ready_requires_worldguard_native_validation": ["tests/test_template_packs.py:test_builtin_guard_pack_selects_and_validates_deterministically"],
}


def main() -> int:
    report = review_template_pack_builder()
    print(report.format_text())
    conformance = native_conformance()
    print(json.dumps(conformance, indent=2, sort_keys=True))
    return 0 if report.ok and conformance["ok"] else 1


if __name__ == "__main__":
    from flowguard.map.runner import run_owner
    raise SystemExit(run_owner(main))
