"""Build real OSM networks or an explicitly synthetic offline fixture."""

import hashlib
import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
import sumo
import sumolib

from .fleet import write_xml
from .zones import map_zones


def binary(name):
    bundled = Path(sumo.SUMO_HOME) / "bin" / (name + (".exe" if os.name == "nt" else ""))
    return str(bundled) if bundled.exists() else sumolib.checkBinary(name)


def run_tool(args, log):
    result = subprocess.run([str(a) for a in args], capture_output=True, text=True, check=False)
    Path(log).write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed; see {log}\n{result.stderr[-3000:]}")


def fetch_osm(city, target):
    bbox = city.bbox
    if not bbox:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": city.place,
                "format": "json",
                "limit": 1,
            },
            headers={"User-Agent": "Simroad/0.1 (local research toolkit)"},
            timeout=60,
        )
        response.raise_for_status()
        records = response.json()
        if not records:
            raise ValueError(f"No OSM result for {city.place!r}")
        s, n, w, e = map(float, records[0]["boundingbox"])
        bbox = w, s, e, n
    w, s, e, n = bbox
    if (e - w) * (n - s) > 0.1:
        raise ValueError(
            "Area too large for the interactive Overpass importer; supply a local OSM/PBF extract"
        )
    response = requests.post(
        city.overpass_url,
        data={"data": f'[out:xml][timeout:90];(way["highway"]({s},{w},{n},{e});>;);out body;'},
        headers={"User-Agent": "Simroad/0.1"},
        timeout=120,
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)
    if root.tag != "osm" or root.find("way") is None or root.find("remark") is not None:
        raise ValueError("Overpass returned an error or an empty road network")
    target.write_bytes(response.content)


def prepare_network(bundle, output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    raw = output / "base.net.xml"
    target = output / "network.net.xml"
    city = bundle.city
    common = ["--sidewalks.guess", "true", "--crossings.guess", "true", "--walkingareas", "true"]
    if city.left_hand:
        common += ["--lefthand", "true"]
    if city.source == "demo":
        run_tool(
            [
                binary("netgenerate"),
                "--grid",
                "--grid.number",
                city.grid_size,
                "--grid.length",
                city.grid_length_m,
                "--default.speed",
                "11.11",
                "--tls.set",
                "B1",
                *common,
                "-o",
                raw,
            ],
            output / "import.log",
        )
    elif city.source == "network":
        shutil.copyfile(bundle.resolve(city.network_file), raw)
    else:
        osm = bundle.resolve(city.osm_file) if city.osm_file else output / "source.osm.xml"
        if not city.osm_file:
            fetch_osm(city, osm)
        if osm.suffix == ".pbf":
            if not shutil.which("osmium"):
                raise ValueError(
                    "PBF input needs osmium-tool on PATH; or convert the extract to .osm.xml first"
                )
            converted = output / "source.osm.xml"
            run_tool(["osmium", "cat", osm, "-o", converted, "--overwrite"], output / "pbf.log")
            osm = converted
        run_tool(
            [
                binary("netconvert"),
                "--osm-files",
                osm,
                "--geometry.remove",
                "true",
                "--tls.guess",
                "true",
                *common,
                "-o",
                raw,
            ],
            output / "import.log",
        )

    net = sumolib.net.readNet(str(raw))
    mapped = map_zones(bundle, net)
    patches = ET.Element("edges")
    affected = {}
    for zone in bundle.zones:
        params = bundle.parameters[zone.id]
        if params.informal_crossing_probability:
            raise ValueError(
                "Probabilistic midblock crossing is not implemented in v0.1; use explicit informal crossings"
            )
        for edge in mapped[zone.id]:
            speed, encroach = affected.get(edge.getID(), (edge.getSpeed(), 0))
            affected[edge.getID()] = (
                min(speed, params.speed_kph / 3.6) if params.speed_kph else speed,
                max(encroach, params.encroachment_fraction),
            )
    for edge_id, (speed, encroach) in affected.items():
        edge_xml = ET.SubElement(patches, "edge", id=edge_id)
        for lane in net.getEdge(edge_id).getLanes():
            if lane.allows("pedestrian") and not lane.allows("passenger"):
                continue
            ET.SubElement(
                edge_xml,
                "lane",
                index=str(lane.getIndex()),
                speed=str(speed),
                width=str(lane.getWidth() * (1 - encroach)),
            )
    write_xml(patches, output / "zones.edg.xml")
    nodes, connections = ET.Element("nodes"), ET.Element("connections")
    kinds = {}
    for crossing in bundle.infrastructure.crossings:
        if not net.hasNode(crossing.node):
            raise ValueError(f"Unknown crossing junction: {crossing.node}")
        kind = "traffic_light" if crossing.kind == "signalized" else "priority"
        if crossing.node in kinds and kinds[crossing.node] != kind:
            raise ValueError("Signalized and unsignalized crossings cannot share one junction")
        kinds[crossing.node] = kind
        for edge_id in crossing.edges:
            edge = net.getEdge(edge_id)
            if crossing.node not in (edge.getFromNode().getID(), edge.getToNode().getID()):
                raise ValueError(f"Crossing edge {edge_id} is not incident to {crossing.node}")
        ET.SubElement(
            connections, "crossing", node=crossing.node, edges=" ".join(crossing.edges), discard="true"
        )
        ET.SubElement(
            connections,
            "crossing",
            node=crossing.node,
            edges=" ".join(crossing.edges),
            priority="true" if crossing.kind != "informal" else "false",
            width=str(crossing.width_m),
        )
    for node, kind in kinds.items():
        ET.SubElement(nodes, "node", id=node, type=kind)
    write_xml(nodes, output / "crossings.nod.xml")
    write_xml(connections, output / "crossings.con.xml")
    run_tool(
        [
            binary("netconvert"),
            "-s",
            raw,
            "--edge-files",
            output / "zones.edg.xml",
            "--node-files",
            output / "crossings.nod.xml",
            "--connection-files",
            output / "crossings.con.xml",
            "--walkingareas",
            "true",
            "-o",
            target,
        ],
        output / "patch.log",
    )
    # A failed crossing must never become a silently missing experiment intervention.
    final = ET.parse(target).getroot()
    for crossing in bundle.infrastructure.crossings:
        matches = [
            e
            for e in final.findall("edge")
            if e.get("function") == "crossing"
            and e.get("id", "").startswith(f":{crossing.node}_c")
            and set(crossing.edges).issubset(set(e.get("crossingEdges", "").split()))
        ]
        if not matches:
            raise ValueError(f"SUMO could not construct crossing at {crossing.node}; see patch.log")
    (output / "network-manifest.json").write_text(
        json.dumps(
            {
                "input_fingerprint": bundle.network_fingerprint(),
                "network_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return target
