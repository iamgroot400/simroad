# Live viewer

Design: a map-first local traffic workbench. The road network occupies the main
surface; a left-aligned sidebar identifies zones and explains their effects.

Palette: paper #eef2f6, ink #26364a, white #ffffff, office blue #356ddd,
school amber #c78b12, residential teal #238672. Market violet, hospital rose and
transit blue-green complete the categorical zone legend. Segoe UI/system sans
is used throughout, with tabular numerals for the clock and counters.

Layout: header and playback controls / [zone list | interactive road map] /
map-integrated live counts. On narrow screens the map precedes the zone list.
The distinctive element is the actual road geometry with labeled activity areas,
rather than decorative cards. No external tiles, fonts, JavaScript or services.

SUMO owns every vehicle position. Zone overlays come from the configured circle,
polygon, or explicit edge geometry. Vehicle symbols have a minimum screen size
for visibility and are not always drawn to physical scale. Signal dots summarize
junction states; they do not represent individual turning movements. Polling is
approximately five times per second, so very short events may not be visible.
The full run metrics and collision output remain the analytical record.

The signal selector exposes fixed timing, queue-responsive control, Adaptive
Webster and Green Wave coordination. Traffic can also be added during a run by
selecting an origin and destination on the map. The server snaps those points to
passenger-car edges, asks SUMO for a route and schedules the requested vehicles
over the chosen departure window.

For large experiments, vehicle creation is processed in bounded batches and SUMO
sizes insertion batches from the detected CPU capacity. SUMO advances one
microscopic run in its stable single-process mode. Only 5,000 moving vehicle
symbols are sent to the canvas, preventing rendering from dominating the run; this
does not remove vehicles from SUMO or the recorded metrics. SUMO's microscopic
solver is CPU-based and does not offload traffic dynamics to an RTX GPU.
