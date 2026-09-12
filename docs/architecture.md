# Architecture

```text
YAML project -> validated Bundle -> netconvert / netgenerate -> network.net.xml
                    |                                      |
                    +-> seeded demand + fleet XML ----------+
                                                           |
                                                 SUMO + TraCI process
                                                           |
                                                registered signal policy
                                                           |
                                tripinfo + collisions + counts + HTML / JSON
                                                           |
                                paired lab / calibration + evidence stamp
```

`config.py` owns schemas, path resolution, fingerprints and startup invariants.
`osm_import.py` owns network construction and safe plain-XML patches.
`zones.py` maps geometry and integrates daily demand pulses.
`fleet.py` converts explicit behavioral profiles to SUMO vehicle types.
`demand.py` produces sorted, seeded departures, walking routes and transit stops.
`engine.py` launches exactly one SUMO process and collects measurements.
`strategies/` holds independent controllers; adding a decorated module registers it.
`lab.py` creates paired experiments through a process pool, returning t intervals.
`calibrate.py` grid-fits uncertain parameters and evaluates held-out seeds.
`report.py` is the single path for report generation and calibration status.

Run artifacts include demand XML, stops, SUMO logs, tripinfo, collision XML,
demand-generation diagnostics, a manifest, and HTML/JSON results. Generated data
stays under `runs/` by default and is excluded from Git. Configuration and code
are intended to be version-controlled together. No server or cloud account is
needed for local runs.

## New policy

Create `src/simroad/strategies/my_policy.py`, derive from `Fixed` to preserve shared
pedestrian service constraints, apply `@register("my_policy")`, and override
`step()`. The constructor receives a TraCI connection and validated bundle.
Avoid importing or modifying city-specific coordinates inside policies.
Do not skip SUMO's yellow/clearance phases. Test with the offline network, then
compare multiple paired seeds against `fixed`.
