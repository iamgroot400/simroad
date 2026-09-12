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
