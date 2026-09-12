import pytest
from pydantic import ValidationError

from simroad.config import Bundle, Fleet, Simulation


def test_step_exceeds_tau_fails():
    b = Bundle("config/project.yaml")
    b.project.simulation.step_length = 0.7
    with pytest.raises(ValueError, match="shortest active tau"):
        b.validate()


def test_step_equal_tau_is_valid():
    b = Bundle("config/project.yaml")
    b.project.simulation.step_length = 0.6
    b.validate()


def test_bad_shares_rejected():
    data = Bundle("config/project.yaml").fleet.model_dump()
    data["types"][0]["share"] = 0.2
    with pytest.raises(ValidationError, match="sum to 1"):
        Fleet.model_validate(data)


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        Simulation(step_lenght=0.5)
