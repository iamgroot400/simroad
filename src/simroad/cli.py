import argparse
import json
import sys
from pathlib import Path

from traci.exceptions import FatalTraCIError, TraCIException

from .calibrate import apply_parameters, calibrate
from .config import Bundle
from .engine import run
from .lab import compare
from .osm_import import prepare_network


def parser():
    p = argparse.ArgumentParser(description="Simroad: reproducible urban traffic experiments using SUMO")
    p.add_argument(
        "--project", default="config/project.yaml", help="Project YAML; paths inside resolve relative to it"
    )
    p.add_argument("--fleet", help="Override fleet YAML (relative to current directory)")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="Validate configuration, including tau/step invariant")
    schema = sub.add_parser("schema", help="Export JSON schemas for authoring configuration")
    schema.add_argument("--output", default="schemas")
    build = sub.add_parser("build", help="Import/build SUMO network and apply zone/infrastructure patches")
    build.add_argument("--output", default="runs/network")
    live = sub.add_parser("serve", help="Open the local live road and vehicle viewer")
    live.add_argument("--network", help="Existing SUMO network; omit to build from project configuration")
    live.add_argument("--output", help="Directory for live runs; defaults to a fresh runs/live-* directory")
    live.add_argument("--port", type=int, default=8765)
    live.add_argument("--no-open", action="store_true", help="Do not open a browser automatically")
    for command in ("run", "compare", "calibrate"):
        c = sub.add_parser(command)
        c.add_argument("--network", default="runs/network/network.net.xml")
        c.add_argument(
            "--output", required=True, help="Fresh run directory; existing runs are never overwritten"
        )
        if command != "calibrate":
            c.add_argument("--calibration", help="Apply fitted parameters and verify calibration evidence")
        if command == "run":
            c.add_argument("--seed", type=int, default=1)
            c.add_argument("--strategy", default="fixed")
            c.add_argument("--gui", action="store_true", help="Open native SUMO live visualization")
        elif command == "compare":
            c.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4, 5])
            c.add_argument("--strategies", nargs="+", default=["fixed", "pressure"])
            c.add_argument("--workers", type=int, default=1)
        else:
            c.add_argument("--observations", required=True, help="CSV: edge,count,begin,end")
            c.add_argument("--source", required=True, help="Survey description, date and measurement method")
            c.add_argument("--kind", choices=["field", "synthetic"], required=True)
            c.add_argument("--demand-scales", nargs="+", type=float, default=[0.75, 1, 1.25])
            c.add_argument("--tau-scales", nargs="+", type=float, default=[1])
            c.add_argument("--motorcycle-shares", nargs="+", type=float, default=[None])
            c.add_argument("--fit-seeds", nargs="+", type=int, default=[101, 102])
            c.add_argument("--validation-seeds", nargs="+", type=int, default=[201, 202])
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "schema":
            from . import config

            output = Path(args.output)
            output.mkdir(parents=True, exist_ok=True)
            for name in ("Project", "City", "Zone", "ZoneParameters", "Fleet", "Demand", "Infrastructure"):
                (output / f"{name.lower()}.schema.json").write_text(
                    json.dumps(getattr(config, name).model_json_schema(), indent=2), encoding="utf-8"
                )
            print(f"Schemas: {output.resolve()}")
            return 0
        bundle = Bundle(args.project, args.fleet)
        if args.command == "validate":
            print(f"Valid: {bundle.project.name} / {bundle.fleet.name}")
            return 0
        if args.command == "build":
            print(prepare_network(bundle, args.output))
            return 0
        if args.command == "serve":
            import uuid

            from .live_view.server import serve

            if not 0 <= args.port <= 65535:
                raise ValueError("Port must be between 0 and 65535")
            output = Path(args.output or ("runs/live-" + uuid.uuid4().hex[:10])).resolve()
            network = (
                Path(args.network).resolve() if args.network else prepare_network(bundle, output / "network")
            )
            if not network.is_file():
                raise ValueError("Network file does not exist")
            serve(bundle, network, output, args.port, not args.no_open)
            return 0
        network = Path(args.network).resolve()
        if not network.exists():
            raise ValueError("Network does not exist; run simroad build first")
        artifact = getattr(args, "calibration", None)
        if artifact:
            evidence = json.loads(Path(artifact).read_text(encoding="utf-8"))
            if evidence["base_fingerprint"] != bundle.fingerprint(network):
                raise ValueError(
                    "Calibration belongs to a different configuration/network. Recalibrate after changes."
                )
            bundle = apply_parameters(bundle, evidence["parameters"])
        if args.command == "run":
            result = run(bundle, network, args.output, args.seed, args.strategy, args.gui, artifact)
        elif args.command == "compare":
            if args.workers < 1:
                raise ValueError("workers must be at least 1")
            result = compare(
                bundle, network, args.output, args.seeds, args.strategies, args.workers, artifact
            )
        else:
            result = calibrate(
                bundle,
                network,
                args.output,
                args.observations,
                args.source,
                args.kind,
                args.demand_scales,
                args.tau_scales,
                args.motorcycle_shares,
                args.fit_seeds,
                args.validation_seeds,
            )
        print(result["calibration"]["label"])
        print(f"Reports: {Path(args.output).resolve()}")
        return 0
    except (ValueError, OSError, RuntimeError, KeyError, TraCIException, FatalTraCIError) as error:
        print(f"simroad: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
