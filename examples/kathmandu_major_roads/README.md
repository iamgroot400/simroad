# Kathmandu major-road map

This project imports OpenStreetMap road geometry for the Kathmandu Ring Road and
city-core extent. It keeps `trunk`, `primary`, and `secondary` roads plus their
short `_link` connectors so interchanges remain routable. Nepal drives on the left.

Mapmandu was an interactive Kathmandu city guide, but no current downloadable
road dataset or public API was available. OpenStreetMap is used as the reproducible
geometry source and must be attributed to OpenStreetMap contributors under ODbL.

Build the map:

```powershell
.\.venv\Scripts\simroad.exe --project examples/kathmandu_major_roads/project.yaml validate
.\.venv\Scripts\simroad.exe --project examples/kathmandu_major_roads/project.yaml build --output runs/kathmandu-major-roads
```

Open `runs/kathmandu-major-roads/network.net.xml` in SUMO GUI or Netedit. The
source extract, import logs, network manifest, and patched network are kept in the
same output directory.

Or launch the editable live viewer directly:

```powershell
.\\run_live.bat --project examples/kathmandu_major_roads/project.yaml
```

In the browser, paint multiple origin and destination areas to distribute seeded
traffic over the city instead of using one entry point. The default mixed fleet
uses weights of 30 motorcycles, 6 cars, and 2 buses. Optional parking brush areas
place in-lane stops on matching routes so illegal parking can create realistic
local bottlenecks. Vehicle destinations stay hidden until that vehicle is clicked.
After the run, use the JSON and CSV links to export queue time, average delay,
departure delay, throughput, collisions, and completion totals.

This is a geometry-only project. It deliberately contains no invented activity
zones or traffic counts. Add surveyed zones/demand before interpreting a traffic run.
