"""Local-only HTTP viewer; one worker thread owns all TraCI interaction."""
from __future__ import annotations

import json
import math
from pathlib import Path
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Condition, Thread
import time
from urllib.parse import urlsplit
import uuid
import webbrowser

import sumolib
import traci.constants as tc

from ..engine import run
from ..report import UNCALIBRATED
from ..zones import map_zones

COLORS = {"school": "#c78b12", "office": "#356ddd", "market": "#9357c6",
          "residential": "#238672", "hospital": "#c85070", "transit": "#287f98"}
ASSETS = Path(__file__).parent


def geometry(bundle, network):
    net = sumolib.net.readNet(str(network), withInternal=True)
    mapped = map_zones(bundle, net)
    roads = []
    for edge in net.getEdges():
        for lane in edge.getLanes():
            roads.append({"id": lane.getID(), "shape": lane.getShape(), "width": lane.getWidth(),
                          "pedestrian": lane.allows("pedestrian") and not lane.allows("passenger"),
                          "crossing": edge.getFunction() == "crossing"})
    zones = []
    for zone in bundle.zones:
        convert = net.convertLonLat2XY if zone.coordinates == "lonlat" else lambda x, y: (x, y)
        item = {"id": zone.id, "type": zone.type, "color": COLORS[zone.type],
                "population": zone.population, "parameters": bundle.parameters[zone.id].model_dump(),
                "edges": [e.getID() for e in mapped[zone.id]]}
        if zone.edges:
            item["paths"] = [e.getShape() for e in mapped[zone.id]]
            points = [p for path in item["paths"] for p in path]
            item["label"] = [sum(p[i] for p in points)/len(points) for i in (0, 1)]
        elif zone.center:
            item["center"] = convert(*zone.center)
            item["radius"] = zone.radius_m
            item["label"] = item["center"]
        else:
            item["polygon"] = [convert(*p) for p in zone.polygon]
            item["label"] = [sum(p[i] for p in item["polygon"])/len(item["polygon"]) for i in (0, 1)]
        zones.append(item)
    sim = bundle.project.simulation
    return {"name": bundle.project.name, "bounds": net.getBoundary(), "roads": roads,
            "zones": zones, "palette": COLORS, "begin": sim.begin, "end": sim.end,
            "source": bundle.city.source, "fleet": {v.id: {"class": v.vclass, "length": v.length,
            "width": v.width} for v in bundle.fleet.types}, "calibration": UNCALIBRATED,
            "signals": [{"id": node.getID(), "position": node.getCoord()} for node in net.getNodes()
                        if node.getType().startswith("traffic_light")]}


class LiveSession:
    def __init__(self, bundle, network, output):
        self.bundle, self.network = bundle, Path(network).resolve()
        self.output = Path(output).resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.map = geometry(bundle, network)
        self.token = secrets.token_urlsafe(32)
        self.condition = Condition()
        self.worker = None
        self.stop_requested = False
        self.paused = False
        self.speed = 10.0
        self.deadline = 0.0
        self.last_frame = 0.0
        self.report = None
        self.state = {"status": "ready", "time": self.map["begin"], "vehicles": [], "people": [],
                      "signals": {}, "metrics": {}, "speed": self.speed, "report": False, "error": None}

    def read(self):
        with self.condition:
            return {**self.state, "speed": self.speed, "token": self.token}

    def control(self, data):
        action = data.get("action")
        with self.condition:
            alive = self.worker is not None and self.worker.is_alive()
            if action == "start":
                if alive:
                    raise ValueError("A run is already active; pause, resume or stop it first")
                seed = data.get("seed", 1)
                strategy = data.get("strategy", "fixed")
                if type(seed) is not int or not 0 <= seed <= 2147483647:
                    raise ValueError("Seed must be an integer between 0 and 2147483647")
                if strategy not in ("fixed", "pressure"):
                    raise ValueError("Choose fixed or pressure")
                self.stop_requested, self.paused = False, False
                self.deadline, self.last_frame, self.report = 0.0, 0.0, None
                self.state = {"status": "starting", "time": self.map["begin"], "vehicles": [], "people": [],
                              "signals": {}, "metrics": {}, "report": False, "error": None}
                self.worker = Thread(target=self._run, args=(seed, strategy), daemon=True)
                self.worker.start()
            elif action == "speed":
                speed = data.get("value")
                if type(speed) not in (float, int) or not math.isfinite(speed) or not 0.25 <= speed <= 100:
                    raise ValueError("Speed must be between 0.25 and 100")
                self.speed, self.deadline = float(speed), 0.0
            elif action in ("pause", "resume", "stop"):
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

    def before_step(self, step):
        with self.condition:
            while self.paused and not self.stop_requested:
                self.condition.wait(0.2)
            if self.stop_requested:
                return False
            now = time.monotonic()
            if not self.deadline:
                self.deadline = now
            self.deadline = max(now, self.deadline) + step/self.speed
            while not self.stop_requested and not self.paused:
                remaining = self.deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.condition.wait(min(remaining, 0.2))
            if self.paused:
                return self.before_step(step)
            return not self.stop_requested

    def snapshot(self, connection, metrics):
        now = time.monotonic()
        if now-self.last_frame < 0.1:
            return
        self.last_frame = now
        vehicles = [{"id": identifier, "position": values[tc.VAR_POSITION], "angle": values[tc.VAR_ANGLE],
                     "type": values[tc.VAR_TYPE], "speed": values[tc.VAR_SPEED]}
                    for identifier, values in connection.vehicle.getAllSubscriptionResults().items()]
        people = [{"id": p, "position": connection.person.getPosition(p)}
                  for p in connection.person.getIDList()]
        signals = {t: connection.trafficlight.getRedYellowGreenState(t) for t in connection.trafficlight.getIDList()}
        with self.condition:
            status = "stopping" if self.stop_requested else "paused" if self.paused else "running"
            self.state = {**self.state, "status": status, "time": connection.simulation.getTime(),
                          "vehicles": vehicles, "people": people, "signals": signals, "metrics": metrics}

    def _run(self, seed, strategy):
        directory = self.output / ("live-" + uuid.uuid4().hex[:12])
        try:
            result = run(self.bundle, self.network, directory, seed, strategy, observer=self)
            with self.condition:
                self.report = directory / "report.html"
                self.state = {**self.state, "status": "stopped" if result["interrupted"] else "finished",
                              "time": self.map["begin"]+result["duration_seconds"], "report": True,
                              "metrics": {"arrived": result["vehicles_arrived"], "departed": result["vehicles_departed"],
                              "collisions": result["collisions"], "pedestrians_arrived": result["pedestrians_arrived"],
                              "stopped_seconds": result["total_stopped_vehicle_seconds"]}}
        except Exception as error:
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
            payload = json.dumps(content, allow_nan=False).encode() if content_type == "application/json" else content
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def valid_host(self):
            return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

        def do_GET(self):
            if not self.valid_host():
                return self.respond(403, {"error": "Local requests only"})
            path = urlsplit(self.path).path
            if path == "/api/map":
                return self.respond(200, session.map)
            if path == "/api/state":
                return self.respond(200, session.read())
            if path == "/report" and session.report:
                return self.respond(200, session.report.read_bytes(), "text/html; charset=utf-8")
            assets = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8")}
            if path in assets:
                name, mime = assets[path]
                return self.respond(200, (ASSETS/name).read_bytes(), mime)
            return self.respond(404, {"error": "Not found"})

        def do_POST(self):
            if not self.valid_host() or not secrets.compare_digest(self.headers.get("X-Simroad-Token", ""), session.token):
                return self.respond(403, {"error": "Refresh the viewer before sending controls"})
            if self.path != "/api/control":
                return self.respond(404, {"error": "Not found"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 4096:
                    raise ValueError("Invalid request size")
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError("Expected a JSON object")
                return self.respond(200, session.control(data))
            except (ValueError, TypeError) as error:
                return self.respond(400, {"error": str(error)})
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(bundle, network, output, port=8765, open_browser=True):
    session = LiveSession(bundle, network, output)
    server = make_server(session, port)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Live viewer: {url}\nPress Ctrl+C in this terminal to close the server.", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        session.close()
        server.server_close()
