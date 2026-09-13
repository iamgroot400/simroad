import json
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from simroad.config import Bundle
from simroad.live_view.server import LiveSession, make_server
from simroad.osm_import import prepare_network


def wait_for(test, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = test()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("Timed out waiting for live simulation")


@pytest.fixture
def live(tmp_path):
    bundle = Bundle("config/project.yaml")
    bundle.project.simulation.end = bundle.project.simulation.begin + 600
    network = prepare_network(bundle, tmp_path / "network")
    session = LiveSession(bundle, network, tmp_path / "runs")
    yield session
    session.close()


@pytest.mark.integration
def test_zone_geometry_and_colors(live):
    zones = live.map["zones"]
    assert len(zones) == 4
    assert len({z["color"] for z in zones}) == 4
    school = next(z for z in zones if z["type"] == "school")
    assert school["center"] == (180, 180)
    assert school["radius"] == 70
    assert school["parameters"]["speed_kph"] == 25
    assert live.map["roads"]


@pytest.mark.integration
def test_real_positions_pause_resume_stop_and_report(live):
    live.control({"action": "speed", "value": 100})
    live.control({"action": "start", "seed": 1, "strategy": "fixed"})
    try:
        frame = wait_for(lambda: live.read() if live.read()["vehicles"] else None)
        assert all(len(v["position"]) == 2 for v in frame["vehicles"])
        assert any(v["type"] in live.map["fleet"] for v in frame["vehicles"])
        with pytest.raises(ValueError, match="already active"):
            live.control({"action": "start"})
        live.control({"action": "pause"})
        time.sleep(0.15)
        paused = live.read()["time"]
        time.sleep(0.2)
        assert live.read()["time"] == paused
        assert live.read()["status"] == "paused"
        live.control({"action": "resume"})
        wait_for(lambda: live.read()["time"] > paused)
        live.control({"action": "stop"})
        wait_for(lambda: live.read()["status"] == "stopped")
        report = json.loads(live.report.with_suffix(".json").read_text(encoding="utf-8"))
        assert report["interrupted"]
        assert report["duration_seconds"] < 600
        assert not report["calibration"]["calibrated"]
    finally:
        live.close()


@pytest.mark.integration
def test_http_assets_control_guard_and_missing_paths(live):
    server = make_server(live, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        assert b"Activity zones" in urlopen(base, timeout=5).read()
        assert b"canvas" in urlopen(base + "/app.js", timeout=5).read()
        req = Request(
            base + "/api/control",
            data=b'{"action":"speed","value":25}',
            headers={"Content-Type": "application/json"},
        )
        for _ in range(8):
            with pytest.raises(HTTPError) as error:
                urlopen(req, timeout=5)
            assert error.value.code == 403
        req.add_header("X-Simroad-Token", live.token)
        assert json.loads(urlopen(req, timeout=5).read())["speed"] == 25
        with pytest.raises(HTTPError) as error:
            urlopen(base + "/../../config/project.yaml", timeout=5)
        assert error.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.integration
def test_invalid_controls_are_rejected(live):
    for speed in (0, -1, float("nan"), float("inf"), 101, "fast"):
        with pytest.raises(ValueError):
            live.control({"action": "speed", "value": speed})
    with pytest.raises(ValueError):
        live.control({"action": "start", "seed": -1})
    with pytest.raises(ValueError):
        live.control({"action": "start", "strategy": "unknown"})
