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
