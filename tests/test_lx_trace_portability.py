"""A separate, explicit portability contract keeps the strict byte test untouched."""
import copy
import importlib.util
import math
from pathlib import Path

import pytest

from src.api.demo_live import load_demo_trace
from src.api.trace_portability import compare_trace_portability


def test_exact_and_forecast_hash_equivalent_are_distinct():
    trace = load_demo_trace()
    assert compare_trace_portability(trace, trace).strict_equal
    altered = copy.deepcopy(trace)
    cert_id = next(iter(altered["inputs"]))
    cell = altered["inputs"][cert_id]["forecast"]["zone_severity"][0]
    cell[1] = math.nextafter(cell[1], math.inf)
    report = compare_trace_portability(altered, trace)
    assert not report.strict_equal and report.hash_equivalent
    assert report.raw_difference_paths and not report.incompatible_paths


@pytest.mark.parametrize("field", ["hazard", "edge_order", "action", "certificate", "config"])
def test_portability_cannot_hide_semantic_or_provenance_changes(field):
    trace = load_demo_trace()
    altered = copy.deepcopy(trace)
    cert_id = next(iter(altered["inputs"]))
    if field == "hazard":
        altered["inputs"][cert_id]["forecast"]["zone_severity"][0][1] += .01
    elif field == "edge_order":
        value = next(v for v in altered["inputs"].values() if any(len(c["edge_ids"]) > 1 for c in v["candidates"]))
        candidate = next(c for c in value["candidates"] if len(c["edge_ids"]) > 1)
        candidate["edge_ids"].reverse()
    elif field == "action":
        altered["certificates"][0]["chosen"]["action_key"] = "Z1->S1"
    elif field == "certificate":
        altered["certificates"][0]["cert_hash"] = "0" * 64
    else:
        altered["config"]["seed"] += 1
    assert not compare_trace_portability(altered, trace).hash_equivalent


def test_independent_reference_cosine_is_precision_stable_at_problematic_angles():
    path = Path(__file__).resolve().parents[1] / "scripts/trace_forensics.py"
    spec = importlib.util.spec_from_file_location("forensics", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    angle = float.fromhex("0x1.e44d077d985b7p-1")
    assert module.reference_cos(angle, 100).hex() == "0x1.2b86d4616a393p-1"
    assert module.reference_cos(angle, 180) == module.reference_cos(angle, 100)
    assert module.reference_cos(0) == 1
    with pytest.raises(ValueError):
        module.reference_cos(-1)
