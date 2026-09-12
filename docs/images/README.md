# README image assets

These PNGs are committed with the project, so GitHub can display them without an
external image host. Both are authored explanatory diagrams, not application
screenshots or predictions.

- `simroad-workflow.png`: the configuration, simulation and comparison workflow.
- `demo-neighborhood.png`: road shapes read from the generated offline SUMO
  network, with labeled demo zones and crossings.

To rebuild, install Pillow (`python -m pip install Pillow`), generate the demo
network with `simroad build --output runs/demo-network`, then run
`python docs/images/generate_diagrams.py` from the repository root. The generator
uses locally available system fonts. Its zone annotations correspond to the
checked-in default demo; update them if that demo changes.
