# Simroad

**Configurable urban traffic experiments, powered by Eclipse SUMO.**

Import OpenStreetMap roads, describe activity zones and a local fleet in YAML,
then run vehicle-by-vehicle and pedestrian-by-pedestrian simulations. Compare
signal policies using identical demand and paired random seeds, with 95%
confidence intervals and explicit calibration status.

Simroad is an early research toolkit. Its example populations and behavior
parameters are illustrative. **Uncalibrated output is not a city forecast.**

## Start here

Python 3.11+ is required. Run every command from this repository's root.
The Python dependency `eclipse-sumo` includes the SUMO binaries.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
simroad validate
simroad build
simroad run --output runs/first-run --seed 1
```

On macOS/Linux, activate with `source .venv/bin/activate`. If PowerShell activation
is restricted, use `.\.venv\Scripts\python.exe -m simroad` instead of `simroad`.

The default configuration runs a **synthetic neighborhood**, including a school,
offices, a market, homes, a signalized crossing, and a zebra crossing. It works
offline after dependency installation. Open `runs/first-run/report.html` for the
report, or add `--gui` to a new run to watch the native SUMO visualization.

Run output directories must be new: previous experiments are not overwritten.

## Compare two policies

```powershell
simroad compare --output runs/policies --strategies fixed pressure --seeds 1 2 3 4 5 6 7 8 9 10 --workers 2
```

Open `runs/policies/comparison.html`. Results include paired Student t confidence
intervals and significance flags for throughput, stopped vehicle time, collision
episodes, and unfinished vehicles. Both policies receive byte-identical demand
for each seed. Parallel workers launch independent SUMO processes.

`fixed` retains SUMO's cyclic signal program with pedestrian minimum service.
`pressure` extends a demanded green or releases an empty one, responds to waiting
pedestrians, and preserves yellow/all-red clearance and minimum crossing times.
It is a simple heuristic, not a claim of an optimal signal controller.

```powershell
simroad --fleet config/fleet_profiles/car_dominant.yaml run --output runs/car-fleet --seed 1
```

Fleet swaps change physical and behavioral parameters, including sublane filtering.
A single fleet-swap run is a functional check, not statistical evidence that one
fleet is better. The policy comparison command pairs strategies within one fleet.

## Use real roads

```powershell
simroad --project examples/osm/project.yaml validate
simroad --project examples/osm/project.yaml build --output runs/real-network
simroad --project examples/osm/project.yaml run --network runs/real-network/network.net.xml --output runs/real-run
```

The real-road example uses an illustrative Kathmandu bounding box; **no city name
or coordinates appear in the engine**. Replace `bbox: [west, south, east, north]`
with your region, use `place: Your neighborhood`, or set `osm_file` to a local
extract. Large `.osm.pbf` inputs require the separate `osmium-tool` CLI for
conversion, or can be converted to `.osm.xml` beforehand.

The example zone locations are not surveyed facilities. Edit their polygons or
centers/radii and populations for your study. Real imports retain or guess OSM
sidewalks and crossings; inspect the result in SUMO Netedit before engineering
use. Explicit crossings use actual SUMO node and edge IDs in `infrastructure.yaml`.
Rebuild after changing road, zone speed/width, or crossing configuration.

## Configuration

| File | Purpose |
| --- | --- |
| `config/project.yaml` | Simulation window, time step and file references |
| `config/city.yaml` | Demo, OSM import, or existing SUMO network |
| `config/zones.yaml` | Zone population, geometry and overrides |
| `config/zone_defaults.yaml` | Editable daily demand pulses and behavior priors for six zone types |
| `config/demand.yaml` | Derive demand from zones and/or add explicit gateway flows |
| `config/fleet_profiles/*.yaml` | Physical, following, sublane and junction behavior by class |
| `config/infrastructure.yaml` | Crossings, transit stops and scheduled routes |

Paths inside a project YAML resolve relative to that file, independent of the
current directory. Zone coordinates default to longitude/latitude; offline demo
zones explicitly use meters in SUMO's `xy` coordinate system. Explicit edge IDs
override spatial matching. Numeric units are documented in the schema field names
and [model assumptions](docs/model-assumptions.md).

Unknown fields, invalid fleet shares, invalid geometry, and time steps longer
than the shortest active vehicle headway fail loudly. Export editor-friendly JSON
schemas with `simroad schema --output schemas`.

## Calibration

Prepare a CSV with one unique network edge per observation, covering the exact
simulation window. Counts represent vehicles entering that edge during the window,
including vehicles initially inserted there; field detectors should match that
measurement definition. Times are seconds since midnight.

```csv
edge,count,begin,end
A1B1,120,27900,29700
B2C2,85,27900,29700
```

Those rows are format examples, **not field observations**. To test the workflow
with invented data, explicitly select `--kind synthetic`.

```powershell
simroad calibrate --output runs/calibration --observations observations.csv --kind field --source "Survey date, location, method and provenance" --demand-scales 0.75 1 1.25 --tau-scales 0.9 1 1.1 --fit-seeds 101 102 --validation-seeds 201 202
simroad run --output runs/calibrated-run --calibration runs/calibration/calibration.json
```

Optional `--motorcycle-shares 0.4 0.6 0.8` fits mix as well. `tau_scale` changes
following headway as a capacity proxy; it is not a direct saturation-flow model.
The fit selects the lowest mean GEH from an explicit grid, then checks independent
validation seeds. Counts are converted to hourly rates for GEH. Passing requires
GEH < 5 at >=85% of observations and GEH < 10 everywhere.

The report code verifies evidence, model/network fingerprint, SUMO version,
field-data provenance and validation statistics. Synthetic observations never
remove the warning. Fitted parameters are automatically applied when an artifact
is supplied, including parallel comparisons. Editing the original configuration
invalidates its calibration. Count calibration does not validate safety, emissions,
pedestrian behavior or unobserved time windows.

## Development

```powershell
python -m pytest
python -m ruff check --config pyproject.toml src tests
```

The tested Python 3.12 dependency snapshot is in `requirements-lock.txt`; install it with
`python -m pip install -r requirements-lock.txt` before the editable install when reproducing this environment.

Tests include SUMO integration. For pure Python checks only, use
`python -m pytest -m "not integration"`. CI runs the full suite on Windows and Linux.
Add a strategy as a module under `src/simroad/strategies/` using the `@register`
decorator. [Architecture](docs/architecture.md) describes the extension points.

## Version 0.1 scope

Implemented: OSM import, configurable zone demand, two fleet profiles, sublane
simulation, speed/width zone effects, signal and priority crossings, scheduled
transit with dwell distributions, parking-obstruction approximation, seeded policy
comparison, GEH fitting, reports, and native SUMO live viewing.

Deferred: automatic midblock road splitting with probabilistic jaywalking,
parking-search circulation, emergency dispatch/preemption, nonresident access
controls, a browser live viewer, and a general OD estimation/calibration framework.
Setting unsupported probabilistic midblock behavior produces an explicit error.
Existing/supplied midblock junctions can have unprioritized informal crossings.

See [model assumptions and limitations](docs/model-assumptions.md) before using
results to evaluate an intervention. OpenStreetMap imports require attribution
to [OpenStreetMap contributors](https://www.openstreetmap.org/copyright).

## Publish on GitHub

All project files live in this `simroad` directory. `.gitignore` excludes the local
environment, generated networks/runs, caches and secrets. Create an empty GitHub
repository named `simroad`, then run:

```powershell
git init -b main
git add .
git commit -m "Initial Simroad traffic simulation toolkit"
git remote add origin https://github.com/YOUR_USERNAME/simroad.git
git push -u origin main
```

The project does not require credentials or API keys. A public repository is not
created automatically. Choose a source-code license before inviting reuse;
dependency licenses and OSM's data license remain separate.
