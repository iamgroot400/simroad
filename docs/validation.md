# Local validation record

Verified on Windows with Python 3.12 and Eclipse SUMO 1.27.1 on 2026-09-12.

- Full suite: 18 tests passed, including actual SUMO vehicle/pedestrian simulation,
  fleet swaps, transit/bay stops, synthetic calibration, stale-network checks,
  seeded demand and statistical invariants.
- Ruff source checks passed.
- A live OpenStreetMap download and netconvert import produced the example network.
- The full 1,800-second OSM example ran successfully. This verifies execution,
  not empirical validity of the generated demand or geometry.
- Six 1,800-second offline simulations compared fixed and pressure policies at
  seeds 11, 22 and 33, with two parallel workers. Each seed's demand XML hash
  matched across policies.
- No reported endpoint had a significant difference at 95% in that three-seed
  comparison. Three seeds are a functional demonstration, not a strong study.
- Collisions occurred and were retained as model-health metrics. All example
  reports remain uncalibrated. No field-count calibration was claimed.

The full artifacts remain locally under `runs/paired-verified` and
`runs/osm-verified`; generated data is excluded from Git. CI is configured for
Windows and Linux but the remote CI jobs have not run yet.


## Live viewer and launchers (2026-09-13)

- Full suite expanded to 26 passing tests, including real SUMO live coordinates,
  zone geometry/colors, pause/resume, interrupted-run reports, local HTTP controls,
  and preservation/reuse of Python environments.
- Headless Microsoft Edge verified zone selection, visible moving vehicles,
  pause/resume, Stop/report, and a 390-pixel mobile viewport without horizontal
  overflow. The desktop screenshot is committed as `docs/images/live-view.png`.
- The Windows batch launcher completed a quick simulation and paired comparison.
  The Bash launcher completed a quick simulation using Git Bash on Windows.
  Native Linux/macOS execution has not been tested locally.
- Source checks include the shared launcher and viewer server. Browser HTML,
  CSS and JavaScript are included in the Python package.
