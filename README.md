# Simroad

<p align="center">
  <strong>Build, run, and compare reproducible urban traffic simulations with Eclipse SUMO.</strong>
</p>

<p align="center">
  <a href="https://github.com/iamgroot400/simroad/actions/workflows/test.yml"><img alt="Tests" src="https://github.com/iamgroot400/simroad/actions/workflows/test.yml/badge.svg"></a>
  <a href="https://github.com/iamgroot400/simroad/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/iamgroot400/simroad"></a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="Eclipse SUMO" src="https://img.shields.io/badge/Engine-Eclipse%20SUMO-0B6E4F">
</p>

![Simroad live viewer showing a SUMO traffic simulation, activity zones, playback controls, and live counters.](docs/images/live-view.png)

Simroad is a local-first toolkit for exploring how roads, traffic signals,
vehicles, pedestrians, and activity zones interact. It combines a visual city
builder, live simulation viewer, repeatable experiments, calibration tools, and
HTML/JSON reporting in one project.

> [!IMPORTANT]
> Simroad is an experimental research toolkit. Results are not predictions of
> real traffic until the model has been calibrated and validated with suitable
> field observations.

## Highlights

- Import real roads from OpenStreetMap or build a synthetic network.
- Draw and edit roads, intersections, crossings, and activity zones visually.
- Simulate cars, motorcycles, buses, and pedestrians with Eclipse SUMO.
- Compare fixed and queue-responsive signal policies across matching random seeds.
- Fit demand and behavior parameters against observed traffic counts.
- Generate reproducible HTML and JSON reports with uncertainty estimates.
- Run locally without an account, cloud service, React, or Node.js.
- Download portable builds with Python, SUMO, and the Kathmandu map included.

## Download

Portable release builds run entirely on your computer and include the Kathmandu
`trunk`, `primary`, and `secondary` road network.

| Platform | Download | Launch |
| --- | --- | --- |
| Windows x64 | [Simroad-windows-X64.zip](https://github.com/iamgroot400/simroad/releases/latest/download/Simroad-windows-X64.zip) | Extract, then double-click `Simroad.exe` |
| macOS Apple Silicon | [Simroad-macos-ARM64.tar.gz](https://github.com/iamgroot400/simroad/releases/latest/download/Simroad-macos-ARM64.tar.gz) | Extract, then run `./Simroad` in Terminal |
| Linux x64 | [Simroad-linux-X64.tar.gz](https://github.com/iamgroot400/simroad/releases/latest/download/Simroad-linux-X64.tar.gz) | Extract, then run `./Simroad` |

[View all releases](https://github.com/iamgroot400/simroad/releases)

The interface opens in your default browser at `127.0.0.1`. It is available only
on the computer running Simroad and is not published to the internet or local
network. Keep the launcher terminal open and press **Ctrl+C** to stop the app.

Unsigned community builds can trigger Windows SmartScreen or macOS Gatekeeper.
Only use packages downloaded from this repository. Phones and tablets cannot run
the bundled SUMO engine.

## Quick start from source

Requirements:

- Python 3.11 or newer; Python 3.12 is recommended
- Internet access during first-time dependency installation

Clone the repository and launch the live viewer:

```bash
git clone https://github.com/iamgroot400/simroad.git
cd simroad
```

Windows:

```powershell
.\run_live.bat
```

macOS or Linux:

```bash
bash run_live.sh
```

The launcher creates or reuses a project-local virtual environment, installs the
required packages, builds the network, and opens the application. Generated files
are written under `runs/` and are never silently overwritten.

## Kathmandu major-road map

The included Kathmandu project uses OpenStreetMap geometry for the Ring Road and
city core. It keeps `trunk`, `primary`, and `secondary` roads together with their
connector links, and configures left-hand traffic for Nepal.

```powershell
.\run_live.bat --project examples/kathmandu_major_roads/project.yaml
```

The source extract is included, so the network can be rebuilt offline. The sample
is geometry-first and deliberately avoids invented traffic counts. Add surveyed
zones, origin/destination demand, and calibration observations before using its
outputs for real-world decisions.

## Visual city builder

![Simroad city editor with roads, junctions, crossings, and zones.](docs/images/city-editor.png)

Open **Edit city** in the live viewer to:

1. Start from the current network or create an empty layout.
2. Draw roads and connected intersections.
3. Configure lane count, speed, direction, and traffic signals.
4. Add zebra or signal-controlled crossings.
5. Add school, office, market, residential, hospital, or transit zones.
6. Build the SUMO network and immediately run the selected scenario.

Layouts can be saved locally and loaded again later. Imported real-world networks
remain viewable even when they are too complex to convert back into the simplified
editor model.

## How it works

![Simroad workflow: configure roads and travelers, simulate in SUMO, and compare repeated experiments.](docs/images/simroad-workflow.png)

1. **Build the network** — use the offline grid, import OpenStreetMap, supply an
   existing SUMO network, or draw a new layout.
2. **Describe demand** — define activity zones, time-varying trip patterns,
   gateway flows, fleet composition, and scheduled transit.
3. **Run SUMO** — Simroad generates deterministic demand, starts an isolated SUMO
   process, applies the selected control strategy, and records measurements.
4. **Compare experiments** — matching demand and seeds are used for paired policy
   comparisons with confidence intervals.
5. **Validate assumptions** — calibration evidence, configuration fingerprints,
   and model limitations are carried into the reports.

## Live viewer

The live interface displays actual vehicle and pedestrian positions from SUMO,
not a pre-rendered animation.

- Start, pause, resume, stop, and repeat a run.
- Select fixed or queue-responsive signal control.
- Change playback speed without changing simulated time steps.
- Pan and zoom with mouse, keyboard, or touch controls.
- Inspect zones, live counts, collision episodes, and completed trips.
- Open the full report after a run finishes or is stopped.

![Custom city running in the Simroad live viewer.](docs/images/custom-city-live.png)

## Command-line usage

After activating a Python environment and installing the project with
`python -m pip install -e ".[dev]"`:

```bash
# Validate configuration
simroad validate

# Build the configured SUMO network
simroad build --output runs/network

# Run one seeded experiment
simroad run --network runs/network/network.net.xml --output runs/first-run --seed 1

# Start the local-only browser viewer
simroad serve --network runs/network/network.net.xml

# Compare two signal policies using paired seeds
simroad compare \
  --network runs/network/network.net.xml \
  --output runs/policies \
  --strategies fixed pressure \
  --seeds 1 2 3 4 5 \
  --workers 2
```

Use `simroad --help` or `simroad <command> --help` for the complete option list.

## Configuration

| File | Purpose |
| --- | --- |
| `config/project.yaml` | Project paths and simulation window |
| `config/city.yaml` | Synthetic, OpenStreetMap, or existing SUMO network source |
| `config/zones.yaml` | Activity-zone geometry and population |
| `config/zone_defaults.yaml` | Demand pulses and behavior assumptions by zone type |
| `config/demand.yaml` | Zone-derived demand and explicit gateway flows |
| `config/fleet_profiles/` | Vehicle dimensions, dynamics, shares, and lateral behavior |
| `config/infrastructure.yaml` | Crossings, stops, and scheduled transit routes |

Paths referenced by a project file resolve relative to that file. Configuration
is validated with Pydantic, and JSON schemas can be exported for editor support:

```bash
simroad schema --output schemas
```

## Calibration

Calibration adjusts uncertain demand and behavior parameters against observed edge
counts. Observations must describe unique network edges and the same time window as
the simulation.

```csv
edge,count,begin,end
A1B1,120,27900,29700
B2C2,85,27900,29700
```

```bash
simroad calibrate \
  --network runs/network/network.net.xml \
  --output runs/calibration \
  --observations observations.csv \
  --kind field \
  --source "Survey date, location, and collection method" \
  --demand-scales 0.75 1 1.25 \
  --tau-scales 0.9 1 1.1 \
  --fit-seeds 101 102 \
  --validation-seeds 201 202
```

Simroad evaluates count fit with GEH and separate validation seeds. A passing count
fit does not validate pedestrian behavior, safety, emissions, or another time
period. See [model assumptions](docs/model-assumptions.md) before interpreting a
scenario.

## Reports and reproducibility

Each run records configuration snapshots, generated demand, SUMO logs, raw XML,
JSON results, and a browser-readable report. Policy comparisons report paired
differences, 95% confidence intervals, and significance flags.

| Metric | Interpretation |
| --- | --- |
| Throughput | Completed vehicle trips per simulated hour |
| Stopped vehicle time | Accumulated queueing time |
| Unfinished/not-inserted | Demand not completed within the simulation window |
| Collision episodes | Distinct SUMO collision episodes requiring investigation |
| Paired confidence interval | Uncertainty in candidate-minus-baseline differences |
| Calibration status | Whether matching field-count evidence passed validation checks |

Random seeds make stochastic demand repeatable. A single run is a functional
scenario, not statistical evidence.

## Project structure

```text
simroad/
├── config/                         Default experiment configuration
├── examples/kathmandu_major_roads/ Kathmandu OSM project and offline extract
├── src/simroad/                    Simulation engine, importer, viewer, and reports
├── tests/                          Unit and SUMO integration tests
├── scripts/                        Development and desktop entry points
├── docs/                           Architecture, assumptions, and screenshots
└── .github/workflows/              Test and desktop-release automation
```

Architecture details are available in [docs/architecture.md](docs/architecture.md).

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check --config pyproject.toml src scripts tests
```

The full test suite launches SUMO and runs on Windows and Linux. Tagged releases
also build and smoke-test portable Windows, macOS, and Linux packages. For Python-
only tests:

```bash
python -m pytest -m "not integration"
```

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a
pull request.

## Current scope and limitations

Implemented features include OpenStreetMap import, configurable activity demand,
mixed vehicle fleets, sublane movement, pedestrian crossings, transit stops,
parking-obstruction approximation, seeded policy comparison, count calibration,
reports, and a local live viewer.

The following are intentionally outside the current scope:

- Automatic midblock splitting with probabilistic jaywalking
- Parking-search circulation
- Emergency dispatch and signal preemption
- Nonresident access-control modeling
- General origin/destination estimation
- Native mobile execution of the SUMO engine

## Data attribution

Kathmandu road geometry is derived from
[OpenStreetMap contributors](https://www.openstreetmap.org/copyright) and is
subject to the Open Database License. Eclipse SUMO is distributed under
EPL-2.0 or GPL-2.0-or-later. Release packages include the relevant SUMO notices.

---

<p align="center">
  Built for transparent, repeatable traffic experiments—not black-box predictions.
</p>
