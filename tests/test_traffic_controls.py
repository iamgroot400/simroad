import time

import pytest
import sumolib

from simroad.config import Bundle
from simroad.engine import run
from simroad.live_view.server import LiveSession
from simroad.osm_import import prepare_network


def wait_for(test, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = test()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("Timed out waiting for traffic control")


@pytest.fixture(scope="module")
def traffic_network(tmp_path_factory):
    root = tmp_path_factory.mktemp("traffic-controls")
    bundle = Bundle("config/project.yaml")
    bundle.project.simulation.end = bundle.project.simulation.begin + 60
    return bundle, prepare_network(bundle, root / "network"), root


@pytest.mark.integration
@pytest.mark.parametrize("strategy", ["webster", "green_wave"])
def test_additional_signal_policies_run(traffic_network, strategy):
    bundle, network, root = traffic_network
    result = run(bundle, network, root / strategy, seed=43, strategy=strategy)
    assert result["strategy"] == strategy
    assert result["vehicles_departed"] > 0


@pytest.mark.integration
def test_map_selected_cars_are_batched_into_live_run(traffic_network):
    bundle, network, root = traffic_network
    bundle.project.simulation.end = bundle.project.simulation.begin + 120
    session = LiveSession(bundle, network, root / "live")
    net = sumolib.net.readNet(str(network))
    origin = list(net.getEdge("A0B0").getShape()[0])
    destination = list(net.getEdge("C3D3").getShape()[-1])
    try:
        queued = session.control(
            {
                "action": "inject",
                "count": "25",
                "spread": 10,
                "origin": origin,
                "destination": destination,
            }
        )
        assert queued["spawn"]["queued"] == 25
        session.control({"action": "speed", "value": 100})
        session.control({"action": "start", "seed": 7, "strategy": "fixed"})
        wait_for(lambda: session.read()["spawn"]["added"] == 25)
        state = wait_for(lambda: session.read() if session.read()["metrics"].get("departed") else None)
        assert state["spawn"]["failed"] == 0
        assert state["metrics"]["active"] >= len(state["vehicles"])
    finally:
        session.close()


@pytest.mark.integration
def test_car_count_has_no_application_cap(traffic_network):
    bundle, network, root = traffic_network
    session = LiveSession(bundle, network, root / "unlimited")
    net = sumolib.net.readNet(str(network))
    try:
        state = session.control(
            {
                "action": "inject",
                "count": "100000",
                "spread": 1800,
                "origin": list(net.getEdge("A0B0").getShape()[0]),
                "destination": list(net.getEdge("C3D3").getShape()[-1]),
            }
        )
        assert state["spawn"]["queued"] == 100000
    finally:
        session.close()
