from types import SimpleNamespace

import pytest

from simroad.calibrate import evaluate, geh
from simroad.engine import CollisionEvents
from simroad.lab import paired_comparison
from simroad.report import calibration_status


def test_paired_ci_uses_differences():
    result = paired_comparison({1: 100, 2: 200, 3: 400}, {1: 110, 2: 210, 3: 410})
    assert result["ci95"] == [10, 10]
    assert result["significant_95"]


def test_insufficient_or_unpaired_seeds_fail():
    with pytest.raises(ValueError):
        paired_comparison({1: 2}, {1: 3})
    with pytest.raises(ValueError):
        paired_comparison({1: 2, 2: 2}, {1: 3, 3: 3})


def test_collision_episodes_not_overlaps():
    counter = CollisionEvents()
    collision = SimpleNamespace(collider="a", victim="b", type="collision")
    for _ in range(5):
        counter.update([collision])
    assert counter.count == 1
    counter.update([])
    counter.update([collision])
    assert counter.count == 2


def test_geh_and_zero():
    assert geh(0, 0) == 0
    assert geh(100, 100) == 0
    assert not evaluate({"x": 1000}, {"x": 100})["passed"]
    assert evaluate({"x": 101}, {"x": 100})["passed"]


def test_no_evidence_cannot_be_calibrated():
    assert not calibration_status(None, "abc", "SUMO")["calibrated"]


def test_calibration_status_checks_provenance_and_fingerprint(tmp_path):
    import json

    path = tmp_path / "evidence.json"
    data = {
        "fingerprint": "abc",
        "sumo_version": "SUMO",
        "observations_kind": "field",
        "observation_source": "Unit test provenance",
        "fit_seeds": [1, 2],
        "validation_seeds": [3, 4],
        "validation": {"modeled_hourly": {"x": 100}, "observed_hourly": {"x": 100}},
    }
    path.write_text(json.dumps(data))
    assert calibration_status(path, "abc", "SUMO")["calibrated"]
    assert not calibration_status(path, "changed", "SUMO")["calibrated"]
    assert not calibration_status(path, "abc", "different version")["calibrated"]
    data["observations_kind"] = "synthetic"
    path.write_text(json.dumps(data))
    assert not calibration_status(path, "abc", "SUMO")["calibrated"]
