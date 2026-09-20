"""Local-only HTTP viewer; one worker thread owns all TraCI interaction."""

from __future__ import annotations

import json
import math
import os
import secrets
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Condition, Thread
from urllib.parse import urlsplit

import sumolib
import traci.constants as tc
from sumolib.geomhelper import distancePointToPolygon

from ..calibrate import apply_parameters, calibrate
from ..engine import run
from ..report import UNCALIBRATED
from ..zones import map_zones
from .calibration import CalibrationJob
from .editor import Layout, compile_layout, from_network

COLORS = {
    "school": "#c78b12",
    "office": "#356ddd",
    "market": "#9357c6",
    "residential": "#238672",
    "hospital": "#c85070",
    "transit": "#287f98",
}
ASSETS = Path(__file__).parent


def geometry(bundle, network):
    net = sumolib.net.readNet(str(network), withInternal=True)
    mapped = map_zones(bundle, net)
    roads = []
    for edge in net.getEdges(withInternal=True):
        for lane in edge.getLanes():
            roads.append(
                {
                    "id": lane.getID(),
                    "edge": edge.getID(),
                    "shape": lane.getShape(),
                    "width": lane.getWidth(),
                    "pedestrian": lane.allows("pedestrian") and not lane.allows("passenger"),
                    "crossing": edge.getFunction() == "crossing",
                }
            )
    zones = []
    for zone in bundle.zones:
        convert = net.convertLonLat2XY if zone.coordinates == "lonlat" else lambda x, y: (x, y)
        item = {
            "id": zone.id,
            "type": zone.type,
            "color": COLORS[zone.type],
            "population": zone.population,
            "parameters": bundle.parameters[zone.id].model_dump(),
            "edges": [e.getID() for e in mapped[zone.id]],
        }
        if zone.edges:
            item["paths"] = [e.getShape() for e in mapped[zone.id]]
            points = [p for path in item["paths"] for p in path]
            item["label"] = [sum(p[i] for p in points) / len(points) for i in (0, 1)]
        elif zone.center:
            item["center"] = convert(*zone.center)
            item["radius"] = zone.radius_m
            item["label"] = item["center"]
        else:
            item["polygon"] = [convert(*p) for p in zone.polygon]
            item["label"] = [sum(p[i] for p in item["polygon"]) / len(item["polygon"]) for i in (0, 1)]
        zones.append(item)
    sim = bundle.project.simulation
    return {
        "name": bundle.project.name,
        "bounds": net.getBoundary(),
        "roads": roads,
        "zones": zones,
        "palette": COLORS,
        "begin": sim.begin,
        "end": sim.end,
        "source": bundle.city.source,
        "fleet": {
            v.id: {"class": v.vclass, "length": v.length, "width": v.width} for v in bundle.fleet.types
        },
        "calibration": UNCALIBRATED,
        "signals": [
            {"id": node.getID(), "position": node.getCoord()}
            for node in net.getNodes()
            if node.getType().startswith("traffic_light")
        ],
    }


class LiveSession:
    def __init__(self, bundle, network, output, layouts=None):
        self.bundle, self.network = bundle, Path(network).resolve()
        self.output = Path(output).resolve()
        self.net = sumolib.net.readNet(str(self.network), withInternal=True)
        cpu_count = os.cpu_count() or 2
        self.cpu_threads = max(1, cpu_count)
        self.spawn_batch_size = max(100, min(8, self.cpu_threads - 1) * 50)
        self.visual_limit = 5000
        self.visualized = set()
        self.spawn_queue = []
        self.injected_added = 0
        self.spawn = {
            "queued": 0,
            "added": 0,
            "failed": 0,
            "message": "Click the map to choose an origin and destination.",
        }
        passenger_types = [item.id for item in bundle.fleet.types if item.vclass == "passenger"]
        self.spawn_type = passenger_types[0] if passenger_types else bundle.fleet.types[0].id
        self.output.mkdir(parents=True, exist_ok=True)
        self.map = geometry(bundle, network)
        self.layout = None
        self.editor_error = None
        try:
            self.layout = from_network(bundle, network)
        except ValueError as error:
            self.editor_error = str(error)
        self.revision = 0
        self.layouts = Path(layouts) if layouts else self.output / "layouts"
        self.layouts.mkdir(parents=True, exist_ok=True)
        self.token = secrets.token_urlsafe(32)
        self.condition = Condition()
        self.worker = None
        self.stop_requested = False
        self.paused = False
        self.speed = 10.0
        self.deadline = 0.0
        self.last_frame = 0.0
        self.report = None
        self.calibration_artifact = None
        self.current_calibration = None
        self.calibration_result = None
        self.calibration_report = None
        self.calibration_progress = None
        self.state = {
            "status": "ready",
            "time": self.map["begin"],
            "vehicles": [],
            "people": [],
            "signals": {},
            "metrics": {},
            "speed": self.speed,
            "report": False,
            "error": None,
        }

    def read(self):
        with self.condition:
            return {
                **self.state,
                "speed": self.speed,
                "token": self.token,
                "revision": self.revision,
                "calibration_result": self.calibration_result,
                "calibration_progress": self.calibration_progress,
                "calibration_applied": self.calibration_artifact is not None
                and self.calibration_report is not None
                and self.calibration_artifact.parent == self.calibration_report.parent,
                "current_calibration": self.current_calibration,
                "spawn": dict(self.spawn),
                "performance": {
                    "threads": self.cpu_threads,
                    "visual_limit": self.visual_limit,
                },
            }

    def _nearest_vehicle_edge(self, point):
        x, y = point
        candidates = []
        try:
            radius = 25
            while not candidates and radius <= 12800:
                candidates = self.net.getNeighboringEdges(x, y, radius, includeJunctions=False)
                radius *= 2
        except (ImportError, RuntimeError):
            candidates = []
        allowed = [
            (edge, distance)
            for edge, distance in candidates
            if not edge.getID().startswith(":") and edge.allows("passenger")
        ]
        if not allowed:
            allowed = [
                (edge, distancePointToPolygon((x, y), edge.getShape()))
                for edge in self.net.getEdges()
                if not edge.getID().startswith(":") and edge.allows("passenger")
            ]
        if not allowed:
            raise ValueError("This map has no road that allows passenger cars")
        return min(allowed, key=lambda item: item[1])[0].getID()

    def control(self, data):
        action = data.get("action")
        with self.condition:
            alive = self.worker is not None and self.worker.is_alive()
            if action == "inject":
                raw_count = data.get("count")
                spread = data.get("spread", 300)
                origin, destination = data.get("origin"), data.get("destination")
                if type(raw_count) is int:
                    count = raw_count
                elif isinstance(raw_count, str) and raw_count.isdecimal():
                    count = int(raw_count)
                else:
                    count = 0
                if count < 1:
                    raise ValueError("Car count must be a positive whole number")
                if type(spread) not in (int, float) or not math.isfinite(spread) or spread < 0:
                    raise ValueError("Spawn window must be zero or more seconds")
                if not all(
                    isinstance(point, list)
                    and len(point) == 2
                    and all(type(value) in (int, float) and math.isfinite(value) for value in point)
                    for point in (origin, destination)
                ):
                    raise ValueError("Choose an origin and destination on the map")
                from_edge = self._nearest_vehicle_edge(origin)
                to_edge = self._nearest_vehicle_edge(destination)
                if from_edge == to_edge:
                    raise ValueError("Choose origin and destination on different road sections")
                self.spawn_queue.append(
                    {
                        "id": uuid.uuid4().hex[:12],
                        "from": from_edge,
                        "to": to_edge,
                        "count": count,
                        "spread": float(spread),
                        "index": 0,
                        "route": None,
                    }
                )
                self.spawn["queued"] += count
                self.spawn["message"] = f"Queued {count:,} cars from {from_edge} to {to_edge}."
                self.condition.notify_all()
                return self.read()
            if action in ("start", "build"):
                seed, strategy = data.get("seed", 1), data.get("strategy", "fixed")
                if type(seed) is not int or not 0 <= seed <= 2147483647:
                    raise ValueError("Seed must be an integer between 0 and 2147483647")
                if strategy not in ("fixed", "pressure", "webster", "green_wave"):
                    raise ValueError("Choose fixed, queue responsive, Adaptive Webster, or Green Wave")
            if action == "calibrate":
                if alive:
                    raise ValueError("Stop the current run before calibrating")
                job = CalibrationJob.model_validate(data.get("job"))
                job.validate_counts(self.bundle, sumolib.net.readNet(str(self.network)))
                self.calibration_progress = None
                self.state = {
                    **self.state,
                    "status": "calibrating",
                    "error": None,
                    "vehicles": [],
                    "people": [],
                    "signals": {},
                }
                self.worker = Thread(target=self._calibrate, args=(job,), daemon=True)
                self.worker.start()
                return self.read()
            if action == "apply_calibration":
                if alive:
                    raise ValueError("Wait for the active operation to finish")
                if not self.calibration_result:
                    raise ValueError("Run calibration first")
                if (
                    self.calibration_artifact
                    and self.calibration_report
                    and self.calibration_artifact.parent == self.calibration_report.parent
                ):
                    raise ValueError("These fitted parameters are already applied")
                evidence = self.calibration_result
                if evidence["base_fingerprint"] != self.bundle.fingerprint(self.network):
                    raise ValueError(
                        "Calibration no longer matches this configuration, or is already applied"
                    )
                self.bundle = apply_parameters(self.bundle, evidence["parameters"])
                self.current_calibration = evidence["calibration"]
                self.calibration_artifact = self.calibration_report.parent / "calibration.json"
                return self.read()
            if action == "save_layout":
                layout = Layout.model_validate(data.get("layout"))
                identifier = uuid.uuid4().hex
                (self.layouts / (identifier + ".json")).write_text(
                    layout.model_dump_json(indent=2), encoding="utf-8"
                )
                return {**self.read(), "saved": identifier}
            if action == "build":
                if alive:
                    raise ValueError("Stop the current simulation before building roads")
                layout = Layout.model_validate(data.get("layout"))
                self.state = {**self.state, "status": "building", "error": None}
                self.worker = Thread(target=self._build, args=(layout, seed, strategy), daemon=True)
                self.worker.start()
            elif action == "start":
                if alive:
                    raise ValueError("A run is already active; pause, resume or stop it first")
                seed = data.get("seed", 1)
                strategy = data.get("strategy", "fixed")
                if type(seed) is not int or not 0 <= seed <= 2147483647:
                    raise ValueError("Seed must be an integer between 0 and 2147483647")
                if strategy not in ("fixed", "pressure", "webster", "green_wave"):
                    raise ValueError("Choose fixed, queue responsive, Adaptive Webster, or Green Wave")
                self.stop_requested, self.paused = False, False
                self.visualized.clear()
                self.injected_added = 0
                self.spawn["added"] = 0
                self.spawn["failed"] = 0
                if not self.spawn_queue:
                    self.spawn["queued"] = 0
                    self.spawn["message"] = "Click the map to choose an origin and destination."
                self.deadline, self.last_frame, self.report = 0.0, 0.0, None
                self.state = {
                    "status": "starting",
                    "time": self.map["begin"],
                    "vehicles": [],
                    "people": [],
                    "signals": {},
                    "metrics": {},
                    "report": False,
                    "error": None,
                }
                self.worker = Thread(target=self._run, args=(seed, strategy), daemon=True)
                self.worker.start()
            elif action == "speed":
                speed = data.get("value")
                if type(speed) not in (float, int) or not math.isfinite(speed) or not 0.25 <= speed <= 100:
                    raise ValueError("Speed must be between 0.25 and 100")
                self.speed, self.deadline = float(speed), 0.0
            elif action in ("pause", "resume", "stop"):
                if self.state["status"] in ("building", "calibrating"):
                    raise ValueError("Wait for the build or calibration batch to finish")
                if not alive:
                    raise ValueError("There is no active run")
                if action == "stop":
                    self.stop_requested = True
                    self.state = {**self.state, "status": "stopping"}
                else:
                    self.paused = action == "pause"
                    self.deadline = 0.0
                    self.state = {**self.state, "status": "paused" if self.paused else "running"}
            else:
                raise ValueError("Unknown control action")
            self.condition.notify_all()
        return self.read()

    def _build(self, layout, seed, strategy):
        try:
            directory = self.output / ("city-" + uuid.uuid4().hex[:12])
            layout, bundle, network = compile_layout(layout, self.bundle, directory)
            new_map = geometry(bundle, network)
            with self.condition:
                self.layout, self.bundle, self.network, self.map = layout, bundle, network, new_map
                self.net = sumolib.net.readNet(str(network), withInternal=True)
                self.visualized.clear()
                self.spawn_queue.clear()
                self.injected_added = 0
                self.revision += 1
                self.calibration_artifact = None
                self.current_calibration = None
                self.calibration_result = None
                self.calibration_report = None
                self.calibration_progress = None
                self.report = None
                self.stop_requested, self.paused = False, False
                self.deadline, self.last_frame = 0.0, 0.0
                self.state = {
                    "status": "starting",
                    "time": new_map["begin"],
                    "vehicles": [],
                    "people": [],
                    "signals": {},
                    "metrics": {},
                    "report": False,
                    "error": None,
                }
            self._run(seed, strategy)
        except Exception as error:  # noqa: BLE001 - expose compilation failures without replacing the city
            with self.condition:
                self.state = {**self.state, "status": "error", "error": str(error)}

    def _calibrate(self, job):
        directory = self.output / ("calibration-" + uuid.uuid4().hex[:12])
        observations = self.output / ("observations-" + uuid.uuid4().hex[:12] + ".csv")
        try:
            observations.write_text(job.observations, encoding="utf-8")

            def progress(done, total, phase, seed):
                with self.condition:
                    self.calibration_progress = {"done": done, "total": total, "phase": phase, "seed": seed}

            result = calibrate(
                self.bundle,
                self.network,
                directory,
                observations,
                job.source,
                job.kind,
                job.demand_scales,
                job.tau_scales,
                [None],
                job.fit_seeds,
                job.validation_seeds,
                progress=progress,
            )
            with self.condition:
                self.calibration_result = result
                self.calibration_report = directory / "report.html"
                self.state = {**self.state, "status": "ready", "error": None}
        except Exception as error:  # noqa: BLE001 - report batch failure to browser
            with self.condition:
                self.state = {**self.state, "status": "error", "error": str(error)}

    def track_vehicle(self, vehicle):
        if len(self.visualized) >= self.visual_limit:
            return False
        self.visualized.add(vehicle)
        return True

    def _inject_batch(self, connection):
        budget = self.spawn_batch_size
        while budget and self.spawn_queue:
            job = self.spawn_queue[0]
            try:
                if job["route"] is None:
                    route = connection.simulation.findRoute(
                        job["from"], job["to"], vType=self.spawn_type
                    ).edges
                    if not route:
                        raise ValueError("No passenger-car route connects the selected points")
                    job["route"] = f"injected_route_{job['id']}"
                    connection.route.add(job["route"], route)
                amount = min(budget, job["count"] - job["index"])
                now = connection.simulation.getTime()
                available = max(0, self.map["end"] - now - self.bundle.project.simulation.step_length)
                spread = min(job["spread"], available)
                for _ in range(amount):
                    index = job["index"]
                    fraction = index / max(1, job["count"] - 1)
                    depart = now + spread * fraction
                    connection.vehicle.add(
                        f"injected_{job['id']}_{index}",
                        job["route"],
                        typeID=self.spawn_type,
                        depart=f"{depart:.3f}",
                        departLane="best",
                        departSpeed="0",
                    )
                    job["index"] += 1
                budget -= amount
                self.injected_added += amount
                self.spawn["queued"] -= amount
                self.spawn["added"] += amount
                self.spawn["message"] = (
                    f"Added {self.spawn['added']:,} cars; {self.spawn['queued']:,} still queued."
                )
                if job["index"] == job["count"]:
                    self.spawn_queue.pop(0)
            except Exception as error:  # noqa: BLE001 - keep the active simulation alive
                failed = job["count"] - job["index"]
                self.spawn["queued"] -= failed
                self.spawn["failed"] += failed
                self.spawn["message"] = str(error)
                self.spawn_queue.pop(0)

    def before_step(self, step, connection):
        with self.condition:
            while True:
                while self.paused and not self.stop_requested:
                    self.condition.wait(0.2)
                if self.stop_requested:
                    return False
                now = time.monotonic()
                if not self.deadline:
                    self.deadline = now
                self.deadline = max(now, self.deadline) + step / self.speed
                while not self.paused:
                    if self.stop_requested:
                        return False
                    remaining = self.deadline - time.monotonic()
                    if remaining <= 0:
                        self._inject_batch(connection)
                        return True
                    self.condition.wait(min(remaining, 0.2))

    def snapshot(self, connection, metrics):
        now = time.monotonic()
        if now - self.last_frame < 0.1:
            return
        self.last_frame = now
        self.visualized.intersection_update(connection.vehicle.getIDList())
        vehicles = [
            {
                "id": identifier,
                "position": values[tc.VAR_POSITION],
                "angle": values[tc.VAR_ANGLE],
                "type": values[tc.VAR_TYPE],
                "speed": values[tc.VAR_SPEED],
            }
            for identifier, values in connection.vehicle.getAllSubscriptionResults().items()
            if tc.VAR_POSITION in values
        ]
        people = [
            {"id": p, "position": connection.person.getPosition(p)} for p in connection.person.getIDList()
        ]
        signals = {
            t: connection.trafficlight.getRedYellowGreenState(t) for t in connection.trafficlight.getIDList()
        }
        with self.condition:
            status = "stopping" if self.stop_requested else "paused" if self.paused else "running"
            self.state = {
                **self.state,
                "status": status,
                "time": connection.simulation.getTime(),
                "vehicles": vehicles,
                "people": people,
                "signals": signals,
                "metrics": metrics,
            }

    def _run(self, seed, strategy):
        directory = self.output / ("live-" + uuid.uuid4().hex[:12])
        try:
            result = run(
                self.bundle,
                self.network,
                directory,
                seed,
                strategy,
                calibration=self.calibration_artifact,
                observer=self,
            )
            with self.condition:
                self.report = directory / "report.html"
                self.state = {
                    **self.state,
                    "status": "stopped" if result["interrupted"] else "finished",
                    "time": self.map["begin"] + result["duration_seconds"],
                    "report": True,
                    "metrics": {
                        "arrived": result["vehicles_arrived"],
                        "departed": result["vehicles_departed"],
                        "collisions": result["collisions"],
                        "pedestrians_arrived": result["pedestrians_arrived"],
                        "stopped_seconds": result["total_stopped_vehicle_seconds"],
                    },
                }
        except Exception as error:  # noqa: BLE001 - report worker failures to the browser
            with self.condition:
                self.state = {**self.state, "status": "error", "error": str(error)}

    def close(self):
        with self.condition:
            self.stop_requested = True
            self.condition.notify_all()
        if self.worker:
            self.worker.join(timeout=30)


def make_server(session, port=8765):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def respond(self, status, content, content_type="application/json"):
            payload = (
                json.dumps(content, allow_nan=False).encode()
                if content_type == "application/json"
                else content
            )
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'",
            )
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def valid_host(self):
            return self.headers.get("Host") in (
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            )

        def do_GET(self):
            if not self.valid_host():
                return self.respond(403, {"error": "Local requests only"})
            path = urlsplit(self.path).path
            if path == "/api/editor":
                if session.layout is None:
                    return self.respond(
                        400,
                        {
                            "error": "This imported network cannot be simplified for editing: "
                            + session.editor_error
                        },
                    )
                return self.respond(200, session.layout.model_dump())
            if path == "/api/layouts":
                return self.respond(
                    200,
                    [
                        {"id": p.stem, "name": json.loads(p.read_text(encoding="utf-8"))["name"]}
                        for p in session.layouts.glob("*.json")
                    ],
                )
            if path.startswith("/api/layout/"):
                identifier = path.rsplit("/", 1)[-1]
                if len(identifier) == 32 and all(c in "0123456789abcdef" for c in identifier):
                    file = session.layouts / (identifier + ".json")
                    if file.is_file():
                        return self.respond(200, json.loads(file.read_text(encoding="utf-8")))
                return self.respond(404, {"error": "Layout not found"})
            if path == "/api/map":
                return self.respond(200, session.map)
            if path == "/api/state":
                return self.respond(200, session.read())
            if path == "/calibration-report" and session.calibration_report:
                return self.respond(200, session.calibration_report.read_bytes(), "text/html; charset=utf-8")
            if path == "/calibration.json" and session.calibration_report:
                return self.respond(
                    200,
                    json.loads(
                        (session.calibration_report.parent / "calibration.json").read_text(encoding="utf-8")
                    ),
                )
            if path == "/report" and session.report:
                return self.respond(200, session.report.read_bytes(), "text/html; charset=utf-8")
            assets = {
                "/": ("index.html", "text/html; charset=utf-8"),
                "/calibration.js": ("calibration.js", "text/javascript; charset=utf-8"),
                "/editor.js": ("editor.js", "text/javascript; charset=utf-8"),
                "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/traffic.js": ("traffic.js", "text/javascript; charset=utf-8"),
                "/style.css": ("style.css", "text/css; charset=utf-8"),
            }
            if path in assets:
                name, mime = assets[path]
                return self.respond(200, (ASSETS / name).read_bytes(), mime)
            return self.respond(404, {"error": "Not found"})

        def do_POST(self):
            # Consume bounded request data before rejecting it. Closing a socket
            # with unread data can reset the connection before Windows receives 403.
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 2000000:
                    raise ValueError("Invalid request size")
                self.connection.settimeout(5)
                body = self.rfile.read(size)
            except (ValueError, TimeoutError) as error:
                return self.respond(400, {"error": str(error)})
            if not self.valid_host() or not secrets.compare_digest(
                self.headers.get("X-Simroad-Token", ""), session.token
            ):
                return self.respond(403, {"error": "Refresh the viewer before sending controls"})
            if self.path != "/api/control":
                return self.respond(404, {"error": "Not found"})
            try:
                data = json.loads(body)
                if not isinstance(data, dict):
                    raise TypeError("Expected a JSON object")
                return self.respond(200, session.control(data))
            except (ValueError, TypeError) as error:
                return self.respond(400, {"error": str(error)})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(bundle, network, output, port=8765, open_browser=True):
    session = LiveSession(bundle, network, output, layouts=Path.cwd() / "scenes")
    server = make_server(session, port)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Live viewer: {url}\nPress Ctrl+C in this terminal to close the server.", flush=True)
    if open_browser:
        try:
            if not webbrowser.open(url, new=2):
                print(f"Browser did not open automatically. Open {url} manually.", flush=True)
        except webbrowser.Error:
            print(f"Browser did not open automatically. Open {url} manually.", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        session.close()
        server.server_close()
