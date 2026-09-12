import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from simroad.config import Bundle
from simroad.demand import generate
from simroad.engine import run
from simroad.osm_import import prepare_network


@pytest.mark.integration
def test_real_sumo_smoke(tmp_path):
    bundle = Bundle("config/project.yaml")
    bundle.project.simulation.end = bundle.project.simulation.begin + 120
    network = prepare_network(bundle, tmp_path / "network")
    root = ET.parse(network).getroot()
    assert root.find("tlLogic") is not None
    assert any(
        e.get("function") == "crossing" and e.get("id").startswith(":C1") for e in root.findall("edge")
    )
    result = run(bundle, network, tmp_path / "run", seed=17, strategy="pressure")
    assert result["vehicles_departed"] > 0
    assert result["demand"]["pedestrians_generated"] > 0
    assert result["collisions"] == 0
    assert not result["calibration"]["calibrated"]
    assert "UNCALIBRATED" in (tmp_path / "run" / "report.html").read_text(encoding="utf-8")
    second = tmp_path / "second"
    second.mkdir()
    generate(bundle, network, second, 17)
    assert (second / "demand.rou.xml").read_bytes() == (tmp_path / "run" / "demand.rou.xml").read_bytes()
    car = Bundle("config/project.yaml", str(Path("config/fleet_profiles/car_dominant.yaml")))
    car.project.simulation.end = bundle.project.simulation.end
    car_run = run(car, network, tmp_path / "car", seed=17)
    assert car_run["demand_sha256"] != result["demand_sha256"]


@pytest.mark.integration
def test_destinations_never_use_internal_edges(tmp_path):
    import sumolib

    from simroad.zones import map_zones

    bundle = Bundle("config/project.yaml")
    network = prepare_network(bundle, tmp_path / "network")
    mapped = map_zones(bundle, sumolib.net.readNet(str(network), withInternal=True))
    assert all(not edge.getID().startswith(":") for edges in mapped.values() for edge in edges)
    output = tmp_path / "demand"
    output.mkdir()
    stats = generate(bundle, network, output, 11)
    assert stats["parking_stops"] > 0
    root = ET.parse(output / "demand.rou.xml").getroot()
    assert all(not stop.get("lane", "").startswith(":") for stop in root.iter("stop"))


@pytest.mark.integration
def test_calibration_pipeline_stays_uncalibrated_for_synthetic_data(tmp_path):
    import json

    from simroad.calibrate import calibrate

    bundle = Bundle("config/project.yaml")
    bundle.project.simulation.end = bundle.project.simulation.begin + 60
    network = prepare_network(bundle, tmp_path / "network")
    observations = tmp_path / "counts.csv"
    observations.write_text("edge,count,begin,end\nA1B1,1,27900,27960\n", encoding="utf-8")
    result = calibrate(
        bundle,
        network,
        tmp_path / "fit",
        observations,
        "Synthetic regression fixture",
        "synthetic",
        [1],
        [1],
        [None],
        [101, 102],
        [201, 202],
    )
    assert not result["calibration"]["calibrated"]
    artifact = json.loads((tmp_path / "fit" / "calibration.json").read_text())
    assert set(artifact["fit_seeds"]).isdisjoint(artifact["validation_seeds"])
    assert "A1B1" in artifact["validation"]["geh"]


@pytest.mark.integration
def test_network_changes_require_rebuild(tmp_path):
    bundle = Bundle("config/project.yaml")
    network = prepare_network(bundle, tmp_path / "network")
    bundle.parameters["school"].speed_kph = 20
    with pytest.raises(ValueError, match="run build again"):
        run(bundle, network, tmp_path / "stale")


@pytest.mark.integration
def test_scheduled_transit_with_offroad_bay(tmp_path):
    from simroad.config import TransitRoute, TransitStop

    bundle = Bundle("config/project.yaml")
    bundle.project.simulation.end = bundle.project.simulation.begin + 120
    bundle.infrastructure.stops = [
        TransitStop(
            id="bay", lane="B0C0_1", start_pos=25, end_pos=50, blocks_lane=False, dwell_mean=5, dwell_std=1
        )
    ]
    bundle.infrastructure.transit_routes = [
        TransitRoute(
            id="local", type="bus", edges=["A0B0", "B0C0", "C0D0"], stops=["bay"], headway_seconds=60
        )
    ]
    network = prepare_network(bundle, tmp_path / "network")
    result = run(bundle, network, tmp_path / "transit", seed=7)
    assert result["demand"]["transit_vehicles"] == 2
    root = ET.parse(tmp_path / "transit" / "demand.rou.xml").getroot()
    assert len(root.findall(".//stop[@busStop='bay'][@parking='true']")) == 2
