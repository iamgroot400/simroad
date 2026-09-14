import pytest

from simroad.live_view.calibration import CalibrationJob


def test_calibration_seed_separation_and_batch_bounds():
    args = {"observations": "edge,count,begin,end", "source": "Survey", "kind": "field"}
    with pytest.raises(ValueError, match="disjoint"):
        CalibrationJob(**args, fit_seeds=[1, 2], validation_seeds=[2, 3])
    with pytest.raises(ValueError, match="12 parameter"):
        CalibrationJob(**args, demand_scales=[1, 2, 3, 4], tau_scales=[1, 2, 3, 4])
    with pytest.raises(ValueError):
        CalibrationJob(**args, fit_seeds=[True, 2])
