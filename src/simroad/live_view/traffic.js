"use strict";

let spawnPick = null;
let spawnOrigin = null;
let spawnDestination = null;

function setSpawnPick(kind) {
  spawnPick = spawnPick === kind ? null : kind;
  $("pick-origin").setAttribute("aria-pressed", String(spawnPick === "origin"));
  $("pick-destination").setAttribute("aria-pressed", String(spawnPick === "destination"));
  canvas.style.cursor = spawnPick ? "crosshair" : "grab";
  refreshTrafficControls();
}

function refreshTrafficControls() {
  if (!state) return;
  const ready = Boolean(spawnOrigin && spawnDestination && connected);
  $("add-cars").disabled = !ready;
  const progress = state.spawn || {};
  if (progress.queued || progress.added || progress.failed) {
    $("spawn-status").textContent = progress.message || "Traffic request updated.";
  } else if (spawnPick) {
    $("spawn-status").textContent = `Click a road to set the ${spawnPick}.`;
  } else if (spawnOrigin && spawnDestination) {
    $("spawn-status").textContent = "Route points selected. Choose a count and add cars.";
  } else {
    $("spawn-status").textContent = "Pick two road locations.";
  }
  if (state.performance) {
    $("performance-note").textContent =
      `${state.performance.threads} logical CPU threads detected · showing up to ` +
      `${state.performance.visual_limit.toLocaleString()} vehicle symbols.`;
  }
}

function drawSpawnPoint(point, color, label) {
  if (!point || window.sceneEditor?.active) return;
  const [x, y] = project(point);
  ctx.save();
  ctx.fillStyle = color;
  ctx.strokeStyle = "white";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.arc(x, y, 8, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#17283b";
  ctx.font = "700 11px Segoe UI, sans-serif";
  ctx.fillText(label, x + 12, y + 4);
  ctx.restore();
}

const baseDraw = draw;
draw = function () {
  baseDraw();
  drawSpawnPoint(spawnOrigin, "#238672", "Origin");
  drawSpawnPoint(spawnDestination, "#c85070", "Destination");
};

const baseUpdate = update;
update = function () {
  baseUpdate();
  if (state?.metrics) {
    $("vehicles").textContent = (state.metrics.active ?? state.vehicles.length).toLocaleString();
  }
  refreshTrafficControls();
};

const basePointerUp = canvas.onpointerup;
canvas.onpointerup = event => {
  if (spawnPick && drag && Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 5) {
    const rectangle = canvas.getBoundingClientRect();
    const point = world([event.clientX - rectangle.left, event.clientY - rectangle.top]);
    if (spawnPick === "origin") spawnOrigin = point;
    else spawnDestination = point;
    drag = null;
    setSpawnPick(null);
    draw();
    return;
  }
  basePointerUp(event);
};

$("pick-origin").onclick = () => setSpawnPick("origin");
$("pick-destination").onclick = () => setSpawnPick("destination");
$("add-cars").onclick = () => {
  const count = $("spawn-count").value.trim();
  const spread = Number($("spawn-spread").value);
  if (!/^[1-9]\d*$/.test(count)) {
    showError("Car count must be a positive whole number.");
    return;
  }
  if (!Number.isFinite(spread) || spread < 0) {
    showError("Spawn window must be zero or more seconds.");
    return;
  }
  control("inject", {count, spread, origin: spawnOrigin, destination: spawnDestination});
};
