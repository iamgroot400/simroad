"""One isolated SUMO process per run. SUMO remains the only physics engine."""

import hashlib
import json
import uuid
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import traci
import traci.constants as tc

from .demand import generate
from .osm_import import binary
from .report import write_report
from .strategies import create


class CollisionEvents:
    """Count episode starts, not an unresolved pair's per-step overlap."""

    def __init__(self):
        self.previous = set()
        self.count = 0

    def update(self, collisions):
        current = {(tuple(sorted((c.collider, c.victim))), c.type) for c in collisions}
        self.count += len(current - self.previous)
        self.previous = current


def run(bundle, network, output, seed=1, strategy="fixed", gui=False, calibration=None, observer=None):
    bundle.validate()
    network, output = Path(network).resolve(), Path(output).resolve()
    if seed < 0:
        raise ValueError("seed must be nonnegative")
    network_manifest = network.parent / "network-manifest.json"
    if network_manifest.exists():
        built = json.loads(network_manifest.read_text(encoding="utf-8"))
        if (
            built["input_fingerprint"] != bundle.network_fingerprint()
            or built["network_sha256"] != hashlib.sha256(network.read_bytes()).hexdigest()
        ):
            raise ValueError("Network or its input configuration changed; run build again before simulating")
    output.mkdir(parents=True, exist_ok=False)
    (output / "config-snapshot.json").write_text(
        json.dumps(
            {
                "project": bundle.project.model_dump(),
                "city": bundle.city.model_dump(),
                "zones": [z.model_dump() for z in bundle.zones],
                "parameters": {k: v.model_dump() for k, v in bundle.parameters.items()},
                "fleet": bundle.fleet.model_dump(),
                "demand": bundle.demand.model_dump(),
                "infrastructure": bundle.infrastructure.model_dump(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    demand_stats = generate(bundle, network, output, seed)
    sim = bundle.project.simulation
    command = [
        binary("sumo-gui" if gui else "sumo"),
        "-n",
        str(network),
        "-r",
        str(output / "demand.rou.xml"),
        "-a",
        str(output / "stops.add.xml"),
        "--begin",
        str(sim.begin),
        "--end",
        str(sim.end),
        "--step-length",
        str(sim.step_length),
        "--lateral-resolution",
        str(sim.lateral_resolution),
        "--seed",
        str(seed),
        "--tripinfo-output",
        str(output / "tripinfo.xml"),
        "--tripinfo-output.write-unfinished",
        "true",
        "--collision.action",
        "warn",
        "--collision.check-junctions",
        "true",
        "--collision.mingap-factor",
        "0",
        "--collision-output",
        str(output / "collisions.xml"),
        "--log",
        str(output / "sumo.log"),
        "--no-step-log",
        "true",
        "--duration-log.disable",
        "true",
        "--time-to-teleport",
        "-1",
    ]
    if gui:
        command += ["--start", "--quit-on-end"]
    label = uuid.uuid4().hex
    connection = None
    collisions = CollisionEvents()
    counts = Counter()
    previous_edges = {}
    arrived, departed, teleports, ped_arrived = 0, 0, 0, 0
    waiting_integral = 0.0
    interrupted = False
    try:
        traci.start(command, label=label, doSwitch=False, stdout=None)
        connection = traci.getConnection(label)
        sumo_version = connection.getVersion()[1]
        policy = create(strategy, connection, bundle)
        while connection.simulation.getTime() < sim.end:
            if observer is not None and not observer.before_step(sim.step_length):
                interrupted = True
                break
            connection.simulationStep()
            for vehicle in connection.simulation.getDepartedIDList():
                connection.vehicle.subscribe(
                    vehicle,
                    [tc.VAR_ROAD_ID, tc.VAR_SPEED]
                    + ([tc.VAR_POSITION, tc.VAR_ANGLE, tc.VAR_TYPE] if observer is not None else []),
                )
            policy.step()
            collisions.update(connection.simulation.getCollisions())
            arrived += connection.simulation.getArrivedNumber()
            departed += connection.simulation.getDepartedNumber()
            ped_arrived += len(connection.simulation.getArrivedPersonIDList())
            teleports += connection.simulation.getStartingTeleportNumber()
            current_edges = {}
            for vehicle, values in connection.vehicle.getAllSubscriptionResults().items():
                edge = values[tc.VAR_ROAD_ID]
                current_edges[vehicle] = edge
                if edge and not edge.startswith(":") and previous_edges.get(vehicle) != edge:
                    counts[edge] += 1
                if values[tc.VAR_SPEED] < 0.1:
                    waiting_integral += sim.step_length
            previous_edges = current_edges
            if observer is not None:
                observer.snapshot(
                    connection,
                    {
                        "arrived": arrived,
                        "departed": departed,
                        "collisions": collisions.count,
                        "pedestrians_arrived": ped_arrived,
                        "stopped_seconds": waiting_integral,
                    },
                )
        unfinished = connection.vehicle.getIDCount()
        pedestrians_active = connection.person.getIDCount()
        elapsed = connection.simulation.getTime() - sim.begin
    finally:
        if connection is not None:
            connection.close()
    trips = ET.parse(output / "tripinfo.xml").getroot().findall("tripinfo")
    finished_trips = [t for t in trips if float(t.get("arrival", "-1")) >= 0]
    mean_loss = (
        (sum(float(t.get("timeLoss")) for t in finished_trips) / len(finished_trips))
        if finished_trips
        else None
    )
    fingerprint = bundle.fingerprint(network)
    result = {
        "seed": seed,
        "strategy": strategy,
        "sumo_version": sumo_version,
        "fingerprint": fingerprint,
        "duration_seconds": elapsed,
        "planned_duration_seconds": sim.end - sim.begin,
        "interrupted": interrupted,
        "vehicles_departed": departed,
        "vehicles_arrived": arrived,
        "vehicles_unfinished": unfinished,
        "vehicles_not_inserted": demand_stats["vehicles_generated"] - departed,
        "pedestrians_arrived": ped_arrived,
        "pedestrians_active": pedestrians_active,
        "collisions": collisions.count,
        "teleports": teleports,
        "mean_completed_time_loss_seconds": mean_loss,
        "total_stopped_vehicle_seconds": waiting_integral,
        "throughput_vehicles_per_hour": arrived * 3600 / elapsed if elapsed else 0,
        "edge_counts": dict(counts),
        "demand": demand_stats,
        "demand_sha256": hashlib.sha256((output / "demand.rou.xml").read_bytes()).hexdigest(),
        "scope": "Counts include edge entries and vehicles inserted on that edge during the configured window.",
    }
    (output / "manifest.json").write_text(
        json.dumps({"command": command, "fingerprint": fingerprint, "sumo_version": sumo_version}, indent=2),
        encoding="utf-8",
    )
    return write_report(
        output / "report",
        f"{bundle.project.name} Â· {strategy} Â· seed {seed}",
        result,
        fingerprint,
        sumo_version,
        calibration,
    )
