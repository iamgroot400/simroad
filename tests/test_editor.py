import pytest
import sumolib

from simroad.config import Bundle
from simroad.engine import run
from simroad.live_view.editor import Layout, compile_layout, planarize


def layout():
    return Layout.model_validate(
        {
            "nodes": [
                {"id": "a", "x": 0, "y": 0},
                {"id": "b", "x": 150, "y": 0},
                {"id": "c", "x": 300, "y": 0},
            ],
            "roads": [
                {"id": "ab", "a": "a", "b": "b", "lanes": 2, "speed": 50},
                {"id": "bc", "a": "b", "b": "c"},
            ],
            "crossings": [{"id": "cross", "node": "b", "road": "ab"}],
            "traffic_per_hour": 600,
        }
    )


def test_intersections_become_shared_junctions():
    city = Layout.model_validate(
        {
            "nodes": [
                {"id": "a", "x": 0, "y": 100},
                {"id": "b", "x": 200, "y": 100},
                {"id": "c", "x": 100, "y": 0},
                {"id": "d", "x": 100, "y": 200},
            ],
            "roads": [{"id": "ab", "a": "a", "b": "b"}, {"id": "cd", "a": "c", "b": "d"}],
        }
    )
    result = planarize(city)
    assert len(result.roads) == 4
    center = next(n for n in result.nodes if n.x == n.y == 100)
    assert all(center.id in (r.a, r.b) for r in result.roads)


def test_reject_missing_nodes_and_short_roads():
    data = layout().model_dump()
    data["roads"][0]["a"] = "missing"
    with pytest.raises(ValueError, match="existing junctions"):
        Layout.model_validate(data)
    data = layout().model_dump()
    data["nodes"][1]["x"] = 2
    with pytest.raises(ValueError, match="8 meters"):
        Layout.model_validate(data)


@pytest.mark.integration
@pytest.mark.parametrize("kind", ["zebra", "signalized"])
def test_custom_city_crossings_lanes_and_real_traffic(tmp_path, kind):
    base = Bundle("config/project.yaml")
    base.project.simulation.end = base.project.simulation.begin + 60
    city = layout()
    city.crossings[0].kind = kind
    _, bundle, network = compile_layout(city, base, tmp_path / "city")
    net = sumolib.net.readNet(str(network), withInternal=True)
    assert sum(l.allows("passenger") for l in net.getEdge("ab_f").getLanes()) == 2
    assert net.getEdge("ab_f").getSpeed() == pytest.approx(50 / 3.6, abs=0.01)
    assert any(e.getFunction() == "crossing" for e in net.getEdges())
    if kind == "signalized":
        assert net.getNode("b").getType() == "traffic_light"
    result = run(bundle, network, tmp_path / "run", 1, "fixed")
    assert result["vehicles_departed"] > 0
    assert result["vehicles_arrived"] > 0
