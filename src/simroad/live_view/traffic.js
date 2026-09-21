"use strict";

let spawnPick = null;
let brushDrawing = false;
let selectedVehicle = null;
const trafficAreas = {origin: [], destination: [], parking: []};
const areaColors = {origin: "#df6f52", destination: "#168d92", parking: "#d39b2c"};

function brushRadius() { return Number($("brush-radius").value); }

function setSpawnPick(kind) {
  spawnPick = spawnPick === kind ? null : kind;
  for (const name of ["origin", "destination", "parking"])
    $("pick-" + name).setAttribute("aria-pressed", String(spawnPick === name));
  canvas.style.cursor = spawnPick ? "crosshair" : "grab";
  refreshTrafficControls();
  draw();
}

function addBrushPoint(kind, point) {
  const points = trafficAreas[kind];
  const last = points.at(-1);
  if (!last || Math.hypot(point[0] - last[0], point[1] - last[1]) >= brushRadius() * 0.3)
    points.push(point);
}

function refreshTrafficControls() {
  if (!state) return;
  const ready = trafficAreas.origin.length && trafficAreas.destination.length && connected;
  $("add-cars").disabled = !ready;
  const progress = state.spawn || {};
  if (progress.queued || progress.added || progress.failed) {
    const types = Object.entries(progress.type_counts || {}).map(([type, count]) => `${type} ${count}`).join(" · ");
    $("spawn-status").textContent = `${progress.message || "Traffic request updated."}${types ? ` ${types}.` : ""}`;
  } else if (spawnPick) {
    $("spawn-status").textContent = `Drag on the map to paint the ${spawnPick} area.`;
  } else if (ready) {
    $("spawn-status").textContent = "Areas ready. Queue the mixed vehicles or keep painting.";
  } else {
    $("spawn-status").textContent = "Paint at least one origin and destination area.";
  }
  if (state.performance) {
    $("performance-note").textContent =
      `${state.performance.threads} logical CPU threads detected · showing up to ` +
      `${state.performance.visual_limit.toLocaleString()} vehicle symbols.`;
  }
  $("queue-time").textContent = Math.round(state.metrics?.stopped_seconds || 0).toLocaleString();
  const delay = state.metrics?.mean_delay;
  $("average-delay").textContent = Number.isFinite(delay) ? delay.toFixed(1) : "—";
  $("report-json").hidden = !state.report;
  $("report-csv").hidden = !state.report;
}

function drawArea(points, kind) {
  if (!points.length || window.sceneEditor?.active) return;
  ctx.save();
  ctx.fillStyle = areaColors[kind] + "24";
  ctx.strokeStyle = areaColors[kind] + "c8";
  ctx.lineWidth = 1.5;
  for (const point of points) {
    const [x, y] = project(point);
    ctx.beginPath();
    ctx.arc(x, y, brushRadius() * view.scale, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
  const [x, y] = project(points[0]);
  ctx.fillStyle = areaColors[kind];
  ctx.font = "700 11px Segoe UI, sans-serif";
  ctx.fillText(kind[0].toUpperCase() + kind.slice(1), x + 8, y - 8);
  ctx.restore();
}

function vehicleById() { return state?.vehicles?.find(vehicle => vehicle.id === selectedVehicle); }

function drawSelectedVehicle() {
  const vehicle = vehicleById();
  if (!vehicle || window.sceneEditor?.active) return;
  const route = new Set(vehicle.route || []);
  ctx.save();
  ctx.strokeStyle = "#09a7c7";
  ctx.lineWidth = 4;
  ctx.globalAlpha = 0.85;
  for (const road of map.roads) if (route.has(road.edge) && !road.pedestrian) { path(road.shape); ctx.stroke(); }
  const destinationRoads = map.roads.filter(road => road.edge === vehicle.destination && !road.pedestrian);
  const destination = destinationRoads.at(-1)?.shape?.at(-1);
  if (destination) {
    const [x, y] = project(destination);
    ctx.globalAlpha = 1;
    ctx.fillStyle = "#09a7c7";
    ctx.strokeStyle = "white";
    ctx.lineWidth = 3;
    ctx.beginPath(); ctx.arc(x, y, 8, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.fillStyle = "#17364a"; ctx.font = "700 11px Segoe UI"; ctx.fillText("Destination", x + 12, y + 4);
  }
  ctx.restore();
}

function updateVehicleDetail() {
  const vehicle = vehicleById();
  $("vehicle-detail").hidden = !vehicle;
  if (!vehicle) return;
  const fleet = map.fleet[vehicle.type] || {};
  $("vehicle-name").textContent = `${fleet.class || vehicle.type} · ${vehicle.id}`;
  $("vehicle-summary").textContent = `${(vehicle.speed * 3.6).toFixed(1)} km/h · ${vehicle.waiting.toFixed(1)} s waiting`;
  $("vehicle-destination").textContent = `Destination edge: ${vehicle.destination}`;
}

const baseDraw = draw;
draw = function () {
  baseDraw();
  drawArea(trafficAreas.origin, "origin");
  drawArea(trafficAreas.destination, "destination");
  drawArea(trafficAreas.parking, "parking");
  drawSelectedVehicle();
};

const baseUpdate = update;
update = function () {
  baseUpdate();
  if (state?.metrics) $("vehicles").textContent = (state.metrics.active ?? state.vehicles.length).toLocaleString();
  if (selectedVehicle && !vehicleById()) selectedVehicle = null;
  updateVehicleDetail();
  refreshTrafficControls();
};

function eventWorld(event) {
  const rectangle = canvas.getBoundingClientRect();
  return world([event.clientX - rectangle.left, event.clientY - rectangle.top]);
}

const basePointerDown = canvas.onpointerdown;
canvas.onpointerdown = event => {
  if (!spawnPick || window.sceneEditor?.active) return basePointerDown(event);
  brushDrawing = true;
  canvas.setPointerCapture(event.pointerId);
  addBrushPoint(spawnPick, eventWorld(event));
  draw();
};

const basePointerMove = canvas.onpointermove;
canvas.onpointermove = event => {
  if (!brushDrawing || !spawnPick) return basePointerMove(event);
  addBrushPoint(spawnPick, eventWorld(event));
  draw();
};

const basePointerUp = canvas.onpointerup;
canvas.onpointerup = event => {
  if (brushDrawing) {
    brushDrawing = false;
    refreshTrafficControls();
    draw();
    return;
  }
  if (!spawnPick && drag && Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 5 && !window.sceneEditor?.active) {
    const point = eventWorld(event);
    let best = null;
    for (const vehicle of state?.vehicles || []) {
      const distance = Math.hypot(vehicle.position[0] - point[0], vehicle.position[1] - point[1]);
      if (distance < 12 / view.scale && (!best || distance < best.distance)) best = {id: vehicle.id, distance};
    }
    if (best) {
      selectedVehicle = best.id;
      drag = null;
      updateVehicleDetail();
      draw();
      return;
    }
  }
  basePointerUp(event);
};

const basePointerCancel = canvas.onpointercancel;
canvas.onpointercancel = event => { brushDrawing = false; basePointerCancel(event); };

for (const kind of ["origin", "destination", "parking"])
  $("pick-" + kind).onclick = () => setSpawnPick(kind);
$("clear-traffic-areas").onclick = () => {
  for (const points of Object.values(trafficAreas)) points.length = 0;
  selectedVehicle = null;
  updateVehicleDetail();
  refreshTrafficControls();
  draw();
};
$("brush-radius").oninput = () => { $("brush-radius-value").textContent = `${brushRadius()} m`; draw(); };
$("close-vehicle").onclick = () => { selectedVehicle = null; updateVehicleDetail(); draw(); };
$("add-cars").onclick = () => {
  const count = $("spawn-count").value.trim();
  const spread = Number($("spawn-spread").value);
  const probability = Number($("parking-probability").value);
  const duration = Number($("parking-duration").value);
  if (!/^[1-9]\d*$/.test(count)) return showError("Vehicle count must be a positive whole number.");
  if (!Number.isFinite(spread) || spread < 0) return showError("Spawn window must be zero or more seconds.");
  if (!Number.isFinite(probability) || probability < 0 || probability > 100)
    return showError("Improper parking chance must be between 0 and 100 percent.");
  if (!Number.isFinite(duration) || duration < 0 || duration > 3600)
    return showError("Parking duration must be between 0 and 3,600 seconds.");
  setSpawnPick(null);
  control("inject", {
    count,
    spread,
    radius: brushRadius(),
    origin_points: trafficAreas.origin,
    destination_points: trafficAreas.destination,
    parking_points: trafficAreas.parking,
    parking_probability: probability / 100,
    parking_duration: duration,
  });
};
