"""Validated browser road layouts compiled into SUMO plain XML, never custom physics."""
from __future__ import annotations

import math
import random
import xml.etree.ElementTree as ET
from itertools import pairwise
from pathlib import Path
from typing import Annotated, Literal

import sumolib
import yaml
from pydantic import Field, model_validator

from ..config import Bundle, Model, ZoneParameters, read_yaml
from ..fleet import write_xml
from ..osm_import import binary, prepare_network, run_tool

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")]
Coordinate = Annotated[float, Field(ge=-1000000, le=1000000)]


class Node(Model):
    id: Identifier
    x: Coordinate
    y: Coordinate
    signal: bool = False


class Road(Model):
    id: Identifier
    a: Identifier
    b: Identifier
    lanes: int = Field(1, ge=1, le=4)
    speed: float = Field(40, ge=10, le=120)
    two_way: bool = True


class EditorCrossing(Model):
    id: Identifier
    node: Identifier
    road: Identifier
    kind: Literal["zebra", "signalized"] = "zebra"
    walk_seconds: float = Field(15, ge=5, le=120)


class EditorZone(Model):
    id: Identifier
    type: Literal["school", "office", "market", "residential", "hospital", "transit"]
    x: Coordinate
    y: Coordinate
    radius: float = Field(70, ge=15, le=1000)
    population: int = Field(200, ge=1, le=100000)
    parameters: dict = Field(default_factory=dict)


class Layout(Model):
    version: Literal[1] = 1
    name: str = Field("My neighborhood", min_length=1, max_length=100)
    nodes: list[Node] = Field(default_factory=list, max_length=500)
    roads: list[Road] = Field(default_factory=list, max_length=1000)
    crossings: list[EditorCrossing] = Field(default_factory=list, max_length=500)
    zones: list[EditorZone] = Field(default_factory=list, max_length=200)
    traffic_per_hour: float = Field(300, ge=0, le=10000)

    @model_validator(mode="after")
    def references(self):
        for objects in (self.nodes, self.roads, self.crossings, self.zones):
            if len({o.id for o in objects}) != len(objects):
                raise ValueError("IDs must be unique within each object type")
        nodes, roads = {n.id: n for n in self.nodes}, {r.id: r for r in self.roads}
        pairs = set()
        for road in self.roads:
            if road.a not in nodes or road.b not in nodes or road.a == road.b:
                raise ValueError("Every road needs two different existing junctions")
            a, b = nodes[road.a], nodes[road.b]
            if math.hypot(a.x-b.x, a.y-b.y) < 8:
                raise ValueError("Road segments must be at least 8 meters long")
            key = tuple(sorted((road.a, road.b)))
            if key in pairs:
                raise ValueError("Duplicate roads between the same junctions; change the existing road instead")
            pairs.add(key)
        for crossing in self.crossings:
            if crossing.node not in nodes or crossing.road not in roads:
                raise ValueError("A crossing must reference an existing road and junction")
            road = roads[crossing.road]
            if crossing.node not in (road.a, road.b):
                raise ValueError("Crossings must sit at a road endpoint; split the road for a midblock crossing")
        for node in self.nodes:
            kinds = {c.kind for c in self.crossings if c.node == node.id}
            if len(kinds) > 1 or (node.signal and "zebra" in kinds):
                raise ValueError("A signal-controlled junction needs signalized crossings; move the zebra crossing midblock")
        return self


def planarize(layout):
    """Split intersecting straight roads so drawn intersections are real junctions."""
    layout = layout.model_copy(deep=True)
    nodes = {n.id: n for n in layout.nodes}
    cuts = {r.id: [(0, r.a), (1, r.b)] for r in layout.roads}
    for i, first in enumerate(layout.roads):
        a, b = nodes[first.a], nodes[first.b]
        dx, dy = b.x-a.x, b.y-a.y
        for second in layout.roads[i+1:]:
            c, d = nodes[second.a], nodes[second.b]
            ex, ey = d.x-c.x, d.y-c.y
            det = dx*ey-dy*ex
            if abs(det) < 1e-8:
                if abs((c.x-a.x)*dy-(c.y-a.y)*dx) < 1e-6:
                    norm = dx*dx+dy*dy
                    bounds = sorted((((c.x-a.x)*dx+(c.y-a.y)*dy)/norm,
                                     ((d.x-a.x)*dx+(d.y-a.y)*dy)/norm))
                    if min(1, bounds[1])-max(0, bounds[0]) > 1e-6:
                        raise ValueError("Roads overlap. Delete the overlapping segment or join at an endpoint")
                continue
            t = ((c.x-a.x)*ey-(c.y-a.y)*ex)/det
            u = ((c.x-a.x)*dy-(c.y-a.y)*dx)/det
            if not (-1e-8 <= t <= 1+1e-8 and -1e-8 <= u <= 1+1e-8):
                continue
            x, y = a.x+t*dx, a.y+t*dy
            found = next((n for n in nodes.values() if math.hypot(n.x-x, n.y-y) < 0.01), None)
            if found is None:
                index = len(nodes)
                while f"junction_{index}" in nodes:
                    index += 1
                found = Node(id=f"junction_{index}", x=x, y=y)
                nodes[found.id] = found
            for road, value in ((first, t), (second, u)):
                cuts[road.id] = [(v, found.id if abs(v-value)<1e-7 else n) for v,n in cuts[road.id]]
                if not any(abs(v-value)<1e-7 for v,_ in cuts[road.id]):
                    cuts[road.id].append((max(0,min(1,value)),found.id))
    new_roads, replacements = [], {}
    used_ids = {r.id for r in layout.roads}
    for road in layout.roads:
        parts = sorted(cuts[road.id])
        replacements[road.id] = []
        for index, ((_, a), (_, b)) in enumerate(pairwise(parts)):
            identifier = road.id if len(parts)==2 else f"{road.id[:55]}_part{index}"
            while identifier in used_ids and identifier != road.id:
                identifier += "x"
            used_ids.add(identifier)
            item = Road(**{**road.model_dump(), "id": identifier, "a": a, "b": b})
            new_roads.append(item)
            replacements[road.id].append(item)
    for crossing in layout.crossings:
        candidates = [r for r in replacements[crossing.road] if crossing.node in (r.a,r.b)]
        if not candidates:
            raise ValueError("A crossing no longer touches its road. Reposition it")
        crossing.road = candidates[0].id
    layout.roads = new_roads
    layout.nodes = [n for n in nodes.values() if any(n.id in (r.a,r.b) for r in new_roads)]
    return Layout.model_validate(layout.model_dump())


def from_network(bundle, network):
    net = sumolib.net.readNet(str(network))
    nodes, node_ids = [], {}
    for node in net.getNodes():
        identifier = f"n{len(nodes)}"
        node_ids[node.getID()] = identifier
        x, y = node.getCoord()
        nodes.append(Node(id=identifier,x=x,y=y,signal=node.getType().startswith("traffic_light")))
    roads, edge_ids, consumed = [], {}, set()
    edges = [e for e in net.getEdges() if e.allows("passenger")]
    by_pair = {(e.getFromNode().getID(),e.getToNode().getID()):e for e in edges}
    for edge in edges:
        if edge.getID() in consumed:
            continue
        a, b = edge.getFromNode().getID(), edge.getToNode().getID()
        reverse = by_pair.get((b,a))
        identifier = f"r{len(roads)}"
        roads.append(Road(id=identifier,a=node_ids[a],b=node_ids[b],two_way=reverse is not None,
                          lanes=min(4,max(1,sum(l.allows("passenger") for l in edge.getLanes()))),
                          speed=max(10,min(120,round(edge.getSpeed()*3.6)))))
        edge_ids[edge.getID()] = identifier
        consumed.add(edge.getID())
        if reverse:
            edge_ids[reverse.getID()] = identifier
            consumed.add(reverse.getID())
    crossings = []
    for crossing in bundle.infrastructure.crossings:
        road = next((edge_ids[e] for e in crossing.edges if e in edge_ids), None)
        if road and crossing.kind != "informal":
            crossings.append(EditorCrossing(id=f"c{len(crossings)}",node=node_ids[crossing.node],
                 road=road,kind=crossing.kind,walk_seconds=crossing.min_walk_seconds))
    zones = []
    for zone in bundle.zones:
        convert = net.convertLonLat2XY if zone.coordinates == "lonlat" else lambda x,y:(x,y)
        if zone.center:
            x,y = convert(*zone.center)
        elif zone.polygon:
            points = [convert(*p) for p in zone.polygon]
            x,y = (sum(p[i] for p in points)/len(points) for i in (0,1))
        else:
            points = [p for e in zone.edges for p in net.getEdge(e).getShape()]
            x,y = (sum(p[i] for p in points)/len(points) for i in (0,1))
        zones.append(EditorZone(id=f"z{len(zones)}",type=zone.type,x=x,y=y,radius=min(1000,max(15,zone.radius_m)),
                               population=zone.population,parameters=bundle.parameters[zone.id].model_dump()))
    return Layout(name=bundle.project.name,nodes=nodes,roads=roads,crossings=crossings,zones=zones)


def compile_layout(layout, base, directory):
    """Create a standalone project; callers only swap active state after this succeeds."""
    layout = planarize(Layout.model_validate(layout))
    if len(layout.roads) < 2:
        raise ValueError("Draw at least two connected road segments before simulating")
    directory = Path(directory).resolve()
    directory.mkdir(parents=True,exist_ok=False)
    node_xml, edge_xml, connections = ET.Element("nodes"), ET.Element("edges"), ET.Element("connections")
    signal_nodes = {c.node for c in layout.crossings if c.kind=="signalized"}
    for node in layout.nodes:
        ET.SubElement(node_xml,"node",id=node.id,x=str(node.x),y=str(node.y),
                      type="traffic_light" if node.signal or node.id in signal_nodes else "priority")
    road_ids = {}
    for road in layout.roads:
        road_ids[road.id] = [road.id+"_f"]+([road.id+"_r"] if road.two_way else [])
        for index, identifier in enumerate(road_ids[road.id]):
            ET.SubElement(edge_xml,"edge",id=identifier,attrib={"from":road.b if index else road.a,
                "to":road.a if index else road.b,"numLanes":str(road.lanes),"speed":str(road.speed/3.6),
                "width":"3.2","sidewalkWidth":"2"})
    for crossing in layout.crossings:
        ET.SubElement(connections,"crossing",node=crossing.node,edges=" ".join(road_ids[crossing.road]),
                      priority="true",width="4")
    for root, name in ((node_xml,"roads.nod.xml"),(edge_xml,"roads.edg.xml"),(connections,"roads.con.xml")):
        write_xml(root,directory/name)
    args = [binary("netconvert"),"--node-files",directory/"roads.nod.xml","--edge-files",directory/"roads.edg.xml",
            "--connection-files",directory/"roads.con.xml","--walkingareas","true",
            "--offset.disable-normalization","true","--crossings.guess","true","-o",directory/"base.net.xml"]
    if base.city.left_hand:
        args += ["--lefthand","true"]
    run_tool(args,directory/"build.log")
    # Verify explicit crossings survived compilation, rather than silently losing them.
    tree = ET.parse(directory/"base.net.xml").getroot()
    for c in layout.crossings:
        if not any(e.get("function")=="crossing" and e.get("id","").startswith(f":{c.node}_c")
                   and set(road_ids[c.road]).issubset(e.get("crossingEdges","").split()) for e in tree.findall("edge")):
            raise ValueError(f"Crossing {c.id} could not be built; move it farther from nearby junctions")
    defaults = read_yaml(base.resolve(base.project.zone_defaults))
    zones = []
    for z in layout.zones:
        parameters = ZoneParameters.model_validate({**defaults[z.type],**z.parameters})
        zones.append({"id":z.id,"type":z.type,"population":z.population,"coordinates":"xy",
                      "center":[z.x,z.y],"radius_m":z.radius,"parameters":parameters.model_dump()})
    net = sumolib.net.readNet(str(directory/"base.net.xml"))
    edges = [e for e in net.getEdges() if all(e.allows(t.vclass) for t in base.fleet.types if t.share>0)]
    pairs = [(a,b) for a in edges for b in edges if a!=b]
    random.Random(0).shuffle(pairs)
    selected = []
    for a,b in pairs:
        if all(net.getShortestPath(a,b,vClass=t.vclass)[0] for t in base.fleet.types if t.share>0):
            selected.append((a.getID(),b.getID()))
        if len(selected)==12:
            break
    if layout.traffic_per_hour and not selected:
        raise ValueError("No connected traffic routes. Join the roads or check one-way directions")
    sim = base.project.simulation.model_dump()
    files = {
        "city.yaml":{"source":"network","network_file":"base.net.xml","left_hand":base.city.left_hand},
        "zones.yaml":{"zones":zones}, "zone_defaults.yaml":defaults,
        "fleet.yaml":base.fleet.model_dump(),
        "infrastructure.yaml":{"crossings":[{"node":c.node,"edges":road_ids[c.road],"kind":c.kind,
            "min_walk_seconds":c.walk_seconds} for c in layout.crossings],"stops":[],"transit_routes":[]},
        "demand.yaml":{"derive_from_zones":bool(zones),"scale":1,"bin_minutes":5,"gateways":[
            {"edge":a,"to_edge":b,"vehicles_per_hour":layout.traffic_per_hour/len(selected),
             "begin_hour":sim["begin"]/3600,"end_hour":sim["end"]/3600} for a,b in selected]},
        "project.yaml":{"name":layout.name,"city":"city.yaml","zones":"zones.yaml","zone_defaults":"zone_defaults.yaml",
                        "fleet":"fleet.yaml","demand":"demand.yaml","infrastructure":"infrastructure.yaml","simulation":sim},
    }
    for name, data in files.items():
        (directory/name).write_text(yaml.safe_dump(data,sort_keys=False),encoding="utf-8")
    (directory/"layout.json").write_text(layout.model_dump_json(indent=2),encoding="utf-8")
    bundle = Bundle(directory/"project.yaml")
    network = prepare_network(bundle,directory/"network")
    return layout,bundle,network
