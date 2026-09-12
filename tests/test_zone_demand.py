import pytest

from simroad.config import Bundle, Pulse
from simroad.zones import expected_trips, pulse_mass


def test_daily_mass_conserved():
    pulse = Pulse(hour=8, sigma_minutes=15, weight=1)
    assert sum(pulse_mass(pulse, t, t + 300) for t in range(0, 86400, 300)) == pytest.approx(1)


def test_school_has_peak_not_flat_rate():
    b = Bundle("config/project.yaml")
    school = b.zones[0]
    p = b.parameters[school.id]
    peak = expected_trips(school, p, 7.5 * 3600, 8 * 3600, "pedestrian", "in")
    noon = expected_trips(school, p, 12 * 3600, 12.5 * 3600, "pedestrian", "in")
    assert peak > 50
    assert noon < 0.001
    total = sum(expected_trips(school, p, 0, 86400, "pedestrian", d) for d in ("in", "out"))
    assert total == pytest.approx(school.population * p.pedestrian_trips_per_person)


def test_zone_numeric_override():
    b = Bundle("config/project.yaml")
    school = b.zones[0]
    p = b.parameters[school.id].model_copy(update={"pedestrian_trips_per_person": 3})
    assert sum(expected_trips(school, p, 0, 86400, "pedestrian", d) for d in ("in", "out")) == pytest.approx(
        540
    )
