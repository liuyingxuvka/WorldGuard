"""Public original-source observations; the oracle is frozen from v1 and third-batch TRUTH.

Historical folders named ``heldout`` are now public development fixtures. These cases are not independent
acceptance. A known-limit row records a miss; a passing regression on it does not mean the slip was caught.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from worldguard.contracts import GuardContract
from worldguard.errors import WorldInputError
from worldguard.io import load_mapping
from worldguard.kernel import run_worldguard
from worldguard.mesh import ModelMeshContract, run_model_mesh


FIXTURES = Path(__file__).parent / "fixtures" / "original_sources"
ORACLE = json.loads((FIXTURES / "expectations.json").read_text(encoding="utf-8"))
SOURCE_FIELDS = {"texts", "aliases", "tables", "decimal", "values"}
SEVERITY = {"PASS": 0, "BOUNDARY_EXCEEDED": 1, "GAP": 2, "FAIL": 3}


def load_seed(folder):
    """Bring the prototype sidecar into the native top-level schema without editing any fixture."""
    meta = load_mapping(folder / "seed.yaml") if (folder / "seed.yaml").is_file() else {}
    if meta.get("mode") == "mesh" or (folder / "mesh.yaml").is_file():
        mode, path = "mesh", folder / "mesh.yaml"
    elif "world" in meta:
        mode, path = "contract", folder / meta["world"]
    else:
        candidates = [p for p in sorted(folder.glob("*.yaml")) if p.name not in {"sources.yaml", "observed_by_hand.yaml"}]
        assert len(candidates) == 1, f"seed needs one unambiguous world: {folder}"
        mode, path = "contract", candidates[0]
    data = load_mapping(path)
    source = {key: value for key, value in load_mapping(folder / "sources.yaml").items() if key in SOURCE_FIELDS}
    return mode, {**data, **source}, meta


def run_seed(mode, data, folder):
    if mode == "mesh":
        return run_model_mesh(ModelMeshContract.from_dict(data, base_dir=folder), base_dir=folder)
    return run_worldguard(GuardContract.from_dict(data, base_dir=folder))


def source_reports(report):
    return list(report.node_reports.values()) if hasattr(report, "node_reports") else [report]


def source_statuses(report):
    return [row for part in source_reports(report) for row in part.checked["source_statuses"]]


def source_colour_counts(report):
    """Compare the prototype's displayed observations, including distinct real failures."""
    counts = Counter()
    parts = source_reports(report)
    for part in parts:
        for kind in ('source_readings', 'source_values'):
            for row in part.checked[kind]:
                colour = 'red' if any(c == 'R' for _, c, _ in row['readings']) else 'green' if row['sourced'] else 'grey'
                counts[colour] += 1
        counts.update(row['colour'] for row in part.checked['source_statuses'])
    uncited = {str(limit) for part in parts for limit in part.scope_limits if str(limit).startswith('TEXT_UNCITED')}
    counts['grey'] += len(uncited)
    failures = set()
    for gap in report.to_dict()['gaps']:
        if gap.get('status') != 'FAIL' or gap.get('code', '').startswith('SOURCE_'):
            continue
        gap = gap.get('evidence', {}).get('gap', gap)
        counterexample = gap.get('counterexample') or {}
        where = gap.get('event_id') or counterexample.get('event_id') or gap.get('edge_id') or gap.get('claim_row')
        detail = {key: gap[key] for key in ('message', 'assertion', 'observed') if key in gap}
        if counterexample:
            detail = {key: counterexample[key] for key in ('at', 'missing_fluents', 'constraint', 'values') if key in counterexample}
        failures.add((gap.get('node_id'), gap['code'], where, json.dumps(detail, sort_keys=True)))
    counts['red'] += len(failures)
    return {colour: counts[colour] for colour in ('green', 'red', 'grey')}


def test_original_fixture_provenance_and_oracle_cover_every_seed():
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    for row in manifest:
        original = FIXTURES / row["path"]
        assert len(original.read_bytes()) == row["bytes"]
        assert hashlib.sha256(original.read_bytes()).hexdigest() == row["sha256"]
    paths = {str(path.parent.relative_to(FIXTURES)) for path in FIXTURES.glob("batch*/**/sources.yaml")}
    assert paths == {row["path"] for row in ORACLE}
    assert len(paths) == 67
    assert sum(row.get("kind") == "known_limit" for row in ORACLE) == 3


@pytest.mark.parametrize("expected", ORACLE, ids=[row["path"] for row in ORACLE])
def test_public_original_seed_observation_matches_frozen_oracle(expected):
    folder = FIXTURES / expected["path"]
    mode, data, _ = load_seed(folder)
    if "input_error" in expected:
        with pytest.raises(WorldInputError, match=expected["input_error"]):
            run_seed(mode, data, folder)
        return
    report = run_seed(mode, data, folder)
    statuses = source_statuses(report)
    has_red = report.status.value == "FAIL" or any(row["colour"] == "red" for row in statuses)
    assert has_red is expected["has_red"]
    assert report.checked["ai_world_status"] == expected["ai_status"]
    worlds = report.checked["text_worlds"]
    assert worlds, "the source-enabled check must expose the text-world result even when no edit was needed"
    actual_text = max((row["status"] for row in worlds), key=SEVERITY.__getitem__)
    assert actual_text == expected["text_status"]
    # The first two batches are strict v1 colour/exit controls. Third-batch TRUTH corrects the
    # prototype's v-prefixed-code false red and lower-case-room-code miss, so retain both records.
    if not expected['path'].startswith('batch3/'):
        assert source_colour_counts(report) == expected['reference_counts']
    for row in statuses:
        assert {"id", "colour", "reason", "source_digest"} <= row.keys()
        assert row["colour"] in {"red", "green", "grey"}
        assert row["id"] and row["reason"]
        assert len(row["source_digest"]) == 64
    # Controls must never be called red; limits retain their visible misses without being scored as caught.
    if expected.get("kind") in {"control", "known_limit"}:
        assert not has_red


def test_unquoted_causal_value_remains_grey_and_uncited_paragraph_visible():
    folder = FIXTURES / "batch3" / "x12_value_without_pointer"
    mode, data, _ = load_seed(folder)
    report = run_seed(mode, data, folder)
    assert report.status.value == "PASS"
    assert any(row["colour"] == "grey" for row in source_statuses(report))
    assert any("TEXT_UNCITED" in str(limit) and "p2" in str(limit) for limit in report.scope_limits)


def test_range_text_worlds_replay_both_real_endpoints():
    folder = FIXTURES / "batch3" / "x07_range_between_minutes"
    mode, data, _ = load_seed(folder)
    report = run_seed(mode, data, folder)
    assert {row["end"]: row["status"] for row in report.checked["text_worlds"]} == {"lo": "PASS", "hi": "FAIL"}


def test_original_seed_sources_are_not_mutated_by_checking():
    folder = FIXTURES / "batch3" / "c04_v_prefixed_version"
    mode, data, _ = load_seed(folder)
    original = deepcopy(data)
    run_seed(mode, data, folder)
    assert data == original


def test_parent_claim_is_red_when_its_child_event_cannot_happen():
    folder = FIXTURES / 'batch1/s1_faithful'
    mode, data, _ = load_seed(folder)
    report = run_seed(mode, data, folder)
    parent = report.node_reports['story']
    assert parent.checked['source_statuses'][0]['colour'] == 'red'
    assert 'e_unlock (EVENT_RELATION_UNMET)' in parent.checked['source_statuses'][0]['reason']
    assert parent.claim_binding['assertions'][0]['source_status'] == parent.checked['source_statuses'][0]


def test_mesh_shared_sources_do_not_report_cited_paragraphs_as_uncited():
    folder = FIXTURES / 'batch3/c07_mesh_two_acts'
    mode, data, _ = load_seed(folder)
    report = run_seed(mode, data, folder)
    assert not any(str(limit).startswith('TEXT_UNCITED') for part in source_reports(report) for limit in part.scope_limits)
    assert source_colour_counts(report) == {'green': 8, 'red': 0, 'grey': 0}
