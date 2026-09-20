from simroad.config import City
from simroad.osm_import import fetch_osm


class Response:
    content = b'<osm version="0.6"><node id="1" lat="27.7" lon="85.3"/><way id="2"><nd ref="1"/></way></osm>'

    def raise_for_status(self):
        return None


def test_fetch_osm_filters_requested_road_hierarchy(monkeypatch, tmp_path):
    captured = {}

    def post(url, data, headers, timeout):
        captured.update(url=url, data=data, headers=headers, timeout=timeout)
        return Response()

    monkeypatch.setattr("simroad.osm_import.requests.post", post)
    city = City(
        source="osm",
        bbox=(85.268, 27.635, 85.392, 27.75),
        left_hand=True,
        highway_classes=["trunk", "primary", "secondary"],
    )
    target = tmp_path / "roads.osm.xml"

    fetch_osm(city, target)

    query = captured["data"]["data"]
    assert 'way["highway"~"^(trunk|primary|secondary)(_link)?$"]' in query
    assert "(27.635,85.268,27.75,85.392)" in query
    assert target.read_bytes() == Response.content


def test_fetch_osm_defaults_to_all_highway_classes(monkeypatch, tmp_path):
    monkeypatch.setattr("simroad.osm_import.requests.post", lambda *args, **kwargs: Response())
    city = City(source="osm", bbox=(85.31, 27.70, 85.32, 27.71))
    fetch_osm(city, tmp_path / "roads.osm.xml")
