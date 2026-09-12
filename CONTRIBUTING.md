# Contributing

Keep city-specific values in configuration. SUMO owns simulation physics.
Add deterministic unit tests for demand/statistics/configuration changes and a
small SUMO integration test for changes to routing or policies. Use paired seeds
for performance claims, preserve model-health metrics, and never remove an
uncalibrated warning without matching validation evidence.

Install with `python -m pip install -e ".[dev]"`, then run `python -m pytest` and
`python -m ruff check --config pyproject.toml src tests`. Do not commit generated
networks, survey data, environments, credentials or run output. Document a new
configuration field's units and modeling assumptions.
