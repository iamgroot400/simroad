"""Seeded microscopic departures with class-specific, connected SUMO routes."""

import itertools
import json
import random
import xml.etree.ElementTree as ET
from pathlib import Path

import sumolib

from .fleet import add_types, write_xml
from .zones import expected_trips, map_zones


def stochastic_count(expected, rng):
    # Poisson arrivals, including non-integer hourly rates.
    count, elapsed = 0, 0.0
    if expected <= 0:
        return 0
    while True:
        elapsed += rng.expovariate(expected)
        if elapsed >= 1:
            return count
        count += 1


def generate(bundle, network, output, seed):
    rng = random.Random(seed)
    net = sumolib.net.readNet(str(network), withInternal=True)
    zones = map_zones(bundle, net)
    sim = bundle.project.simulation
    root = ET.Element("routes")
    add_types(root, bundle.fleet)
    for zone in bundle.zones:
        ET.SubElement(
            root,
            "vType",
            id=f"ped_{zone.id}",
            vClass="pedestrian",
            maxSpeed=str(bundle.parameters[zone.id].pedestrian_speed),
            speedDev="0.1",
        )
    normal = [e for e in net.getEdges() if not e.getID().startswith(":")]
    events = []
    stats = {
        "vehicles_requested": 0,
        "pedestrians_requested": 0,
        "vehicles_generated": 0,
        "pedestrians_generated": 0,
        "unroutable": 0,
        "parking_stops": 0,
        "transit_vehicles": 0,
    }
    types = bundle.fleet.types
    active = [t for t in types if t.share > 0]
    path_cache = {}

    def route(a, b, vclass):
        key = (a.getID(), b.getID(), vclass)
        if key not in path_cache:
            path_cache[key] = net.getShortestPath(a, b, vClass=vclass)[0]
        return path_cache[key]

    def emit(begin, end, zone, mode, direction, count, explicit=None):
        for _ in range(count):
            depart = rng.uniform(begin, end)
            vehicle_type = rng.choices(active, weights=[t.share for t in active])[0]
            vclass = vehicle_type.vclass if mode == "vehicle" else "pedestrian"
            stats["vehicles_requested" if mode == "vehicle" else "pedestrians_requested"] += 1
            local = zones[zone.id] if zone else normal
            available_local = [e for e in local if e.allows(vclass)]
            available_external = [e for e in normal if e.allows(vclass) and e not in local]
            if not available_external:
                available_external = [e for e in normal if e.allows(vclass)]
            found = None
            if explicit:
                a, b = net.getEdge(explicit.edge), net.getEdge(explicit.to_edge)
                if a.allows(vclass) and b.allows(vclass):
                    found = route(a, b, vclass)
            elif available_local and available_external:
                for _attempt in range(40):
                    a, b = rng.choice(available_external), rng.choice(available_local)
                    if direction == "out":
                        a, b = b, a
                    if a != b:
                        found = route(a, b, vclass)
                        if found:
                            break
            if not found:
                stats["unroutable"] += 1
                continue
            event_id = f"{'v' if mode == 'vehicle' else 'p'}{len(events)}"
            if mode == "vehicle":
                elem = ET.Element(
                    "vehicle",
                    id=event_id,
                    type=vehicle_type.id,
                    depart=f"{depart:.3f}",
                    departLane="best",
                    departSpeed="0",
                )
                ET.SubElement(
                    elem, "route", edges=" ".join(e.getID() for e in found if not e.getID().startswith(":"))
                )
                if zone and direction == "in":
                    p = bundle.parameters[zone.id]
                    if rng.random() < p.parking_search_probability:
                        lanes = [lane for lane in found[-1].getLanes() if lane.allows(vclass)]
                        lane = lanes[-1]
                        ET.SubElement(
                            elem,
                            "stop",
                            lane=lane.getID(),
                            endPos=str(max(1, lane.getLength() - 5)),
                            duration=str(p.parking_search_seconds),
                            parking="false",
                        )
                        stats["parking_stops"] += 1
                stats["vehicles_generated"] += 1
            else:
                elem = ET.Element("person", id=event_id, type=f"ped_{zone.id}", depart=f"{depart:.3f}")
                ET.SubElement(
                    elem, "walk", edges=" ".join(e.getID() for e in found if not e.getID().startswith(":"))
                )
                stats["pedestrians_generated"] += 1
            events.append((depart, elem))

    if bundle.demand.derive_from_zones:
        begin = sim.begin
        while begin < sim.end:
            end = min(begin + bundle.demand.bin_minutes * 60, sim.end)
            for zone in bundle.zones:
                for mode in ("vehicle", "pedestrian"):
                    for direction in ("in", "out"):
                        expectation = expected_trips(
                            zone, bundle.parameters[zone.id], begin, end, mode, direction
                        )
                        emit(
                            begin,
                            end,
                            zone,
                            mode,
                            direction,
                            stochastic_count(expectation * bundle.demand.scale, rng),
                        )
            begin = end
    for gateway in bundle.demand.gateways:
        begin, end = max(sim.begin, gateway.begin_hour * 3600), min(sim.end, gateway.end_hour * 3600)
        if end > begin:
            emit(
                begin,
                end,
                None,
                "vehicle",
                "in",
                stochastic_count(gateway.vehicles_per_hour * (end - begin) / 3600 * bundle.demand.scale, rng),
                explicit=gateway,
            )

    additional = ET.Element("additional")
    stop_map = {s.id: s for s in bundle.infrastructure.stops}
    if len(stop_map) != len(bundle.infrastructure.stops):
        raise ValueError("Transit stop IDs must be unique")
    for stop in stop_map.values():
        lane = net.getLane(stop.lane)
        if not 0 <= stop.start_pos < stop.end_pos <= lane.getLength():
            raise ValueError(f"Invalid positions for stop {stop.id}")
        ET.SubElement(
            additional,
            "busStop",
            id=stop.id,
            lane=stop.lane,
            startPos=str(stop.start_pos),
            endPos=str(stop.end_pos),
        )
    for service in bundle.infrastructure.transit_routes:
        if service.type not in {t.id for t in types}:
            raise ValueError(f"Unknown transit vehicle type {service.type}")
        service_type = next(t for t in types if t.id == service.type)
        service_edges = [net.getEdge(e) for e in service.edges]
        for a, b in itertools.pairwise(service_edges):
            if (
                b not in a.getOutgoing()
                or not a.allows(service_type.vclass)
                or not b.allows(service_type.vclass)
            ):
                raise ValueError(f"Transit service {service.id}: disconnected or disallowed route")
        depart = sim.begin
        while depart < sim.end:
            elem = ET.Element(
                "vehicle",
                id=f"bus_{service.id}_{stats['transit_vehicles']}",
                type=service.type,
                depart=str(depart),
            )
            ET.SubElement(elem, "route", edges=" ".join(service.edges))
            for stop_id in service.stops:
                stop = stop_map[stop_id]
                if net.getLane(stop.lane).getEdge().getID() not in service.edges:
                    raise ValueError(f"Stop {stop_id} is outside service {service.id}")
                if rng.random() <= stop.stop_probability:
                    ET.SubElement(
                        elem,
                        "stop",
                        busStop=stop_id,
                        duration=str(max(0, rng.gauss(stop.dwell_mean, stop.dwell_std))),
                        parking="false" if stop.blocks_lane else "true",
                    )
            events.append((depart, elem))
            stats["transit_vehicles"] += 1
            stats["vehicles_generated"] += 1
            stats["vehicles_requested"] += 1
            depart += service.headway_seconds
    for _, elem in sorted(events, key=lambda x: x[0]):
        root.append(elem)
    output = Path(output)
    write_xml(root, output / "demand.rou.xml")
    write_xml(additional, output / "stops.add.xml")
    (output / "demand-summary.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    if stats["unroutable"]:
        raise ValueError(
            f"{stats['unroutable']} trips are unroutable; inspect demand-summary.json and network/zone connectivity"
        )
    return stats
