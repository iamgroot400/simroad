"""Shared, self-contained launcher. Bootstrap uses only Python's standard library."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import uuid
import webbrowser
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def execute(command):
    print("\n> " + subprocess.list2cmdline([str(x) for x in command]), flush=True)
    subprocess.run([str(x) for x in command], cwd=ROOT, check=True)


def env_python(directory):
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def healthy(python, tests=False):
    probe = (
        "import pydantic_core._pydantic_core, numpy, scipy, pyproj, yaml, sumo, traci, sumolib, simroad.cli"
    )
    if tests:
        probe += ", pytest"
    probe += (
        "; from pathlib import Path; import simroad; assert Path(simroad.__file__).resolve().is_relative_to(Path("
        + repr(str(ROOT))
        + "))"
    )
    try:
        result = subprocess.run(
            [str(python), "-c", probe], cwd=ROOT, capture_output=True, text=True, check=False
        )
        return result.returncode == 0
    except OSError:
        return False


def bootstrap(tests=False):
    for directory in (ROOT / ".venv", ROOT / ".venv-runner"):
        python = env_python(directory)
        if python.exists() and healthy(python, tests):
            print(f"Using {python}", flush=True)
            return python
    # Preserve any broken/mixed environment. Never recreate it in place.
    directory = ROOT / ".venv-runner"
    if directory.exists():
        directory = ROOT / (".venv-runner-" + uuid.uuid4().hex[:8])
    print("Creating a clean project-local environment; existing environments are preserved.", flush=True)
    base = getattr(sys, "_base_executable", sys.executable)
    execute([base, "-m", "venv", str(directory)])
    python = env_python(directory)
    execute([python, "-m", "pip", "install", "-e", str(ROOT) + ("[dev]" if tests else "")])
    if not healthy(python, tests):
        raise RuntimeError(
            "Dependencies could not be imported. Check the install output and try Python 3.12."
        )
    return python


def arguments(argv=None):
    p = argparse.ArgumentParser(
        description="Set up Simroad and open its browser simulator; use --batch for experiments."
    )
    p.add_argument(
        "--project", default="config/project.yaml", help="Project YAML, relative to the repository"
    )
    p.add_argument("--fleet", help="Optional fleet YAML, relative to the repository")
    p.add_argument(
        "--seeds", type=int, nargs="+", help="Comparison seeds; default 1 2 3 4 5, or 1 2 in quick mode"
    )
    p.add_argument("--workers", type=int, default=2, help="Independent SUMO processes (default 2)")
    p.add_argument(
        "--quick", action="store_true", help="Run only the first 120 simulated seconds and fewer seeds"
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--web", dest="web", action="store_true", help="Open the browser simulator (default)")
    mode.add_argument(
        "--batch",
        dest="web",
        action="store_false",
        help="Run simulations/comparisons and open the final report",
    )
    p.set_defaults(web=True)
    p.add_argument("--port", type=int, default=8765, help="Local live viewer port")
    p.add_argument("--gui", action="store_true", help="Watch the first run in SUMO's native viewer")
    p.add_argument("--skip-compare", action="store_true", help="Only build and run one simulation")
    p.add_argument("--tests", action="store_true", help="Also install development dependencies and run tests")
    p.add_argument(
        "--no-open",
        action="store_true",
        help="Do not automatically open the browser simulator or completed report",
    )
    p.add_argument("--ready", action="store_true", help=argparse.SUPPRESS)
    return p.parse_args(argv)


def pipeline(args):
    import yaml

    project = (ROOT / args.project).resolve()
    if not project.is_file():
        raise ValueError(f"Project file does not exist: {project}")
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    output = ROOT / "runs" / ("auto-" + stamp)
    output.mkdir(parents=True, exist_ok=False)
    if args.quick:
        config = yaml.safe_load(project.read_text(encoding="utf-8"))
        # Relocated YAML must retain references to the original configuration files.
        from simroad.config import Project

        validated = Project.model_validate(config)
        for key in ("city", "zones", "zone_defaults", "fleet", "demand", "infrastructure"):
            config[key] = str((project.parent / getattr(validated, key)).resolve())
        sim = validated.simulation.model_dump()
        sim["end"] = min(sim["end"], sim["begin"] + 120)
        config["simulation"] = sim
        config["name"] = validated.name + " (quick smoke run)"
        project = output / "quick-project.yaml"
        project.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        print("Quick mode checks execution only; it is not a full study.", flush=True)
    prefix = [sys.executable, "-m", "simroad", "--project", str(project)]
    if args.fleet:
        prefix += ["--fleet", str((ROOT / args.fleet).resolve())]
    execute(prefix + ["validate"])
    if args.tests:
        execute([sys.executable, "-m", "pytest", "-q", "--basetemp", str(output / "test-temp")])
    network_dir = output / "network"
    execute(prefix + ["build", "--output", str(network_dir)])
    network = network_dir / "network.net.xml"
    seeds = args.seeds or ([1, 2] if args.quick else [1, 2, 3, 4, 5])
    if args.web:
        execute(
            prefix
            + ["serve", "--network", str(network), "--output", str(output / "live"), "--port", str(args.port)]
            + (["--no-open"] if args.no_open else [])
        )
        return
    execute(
        prefix
        + ["run", "--network", str(network), "--output", str(output / "simulation"), "--seed", str(seeds[0])]
        + (["--gui"] if args.gui else [])
    )
    report = output / "simulation/report.html"
    if not args.skip_compare:
        execute(
            prefix
            + [
                "compare",
                "--network",
                str(network),
                "--output",
                str(output / "comparison"),
                "--strategies",
                "fixed",
                "pressure",
                "--workers",
                str(args.workers),
                "--seeds",
                *map(str, seeds),
            ]
        )
        report = output / "comparison/comparison.html"
    print(f"\nFinished. Report: {report}\nAll output: {output}", flush=True)
    print("Results are uncalibrated. Field calibration requires your observed traffic counts.", flush=True)
    if not args.no_open:
        try:
            if not webbrowser.open(report.as_uri()):
                print("Open the report path above manually to view it.")
        except webbrowser.Error:
            print("Open the report path above manually to view it.")


def main(argv=None):
    args = arguments(argv)
    if args.gui and args.web:
        raise ValueError("Use --batch --gui for the native SUMO viewer, or omit --gui for the browser")
    if args.workers < 1:
        raise ValueError("--workers must be positive")
    if args.seeds and (any(s < 0 for s in args.seeds) or len(set(args.seeds)) != len(args.seeds)):
        raise ValueError("--seeds must contain distinct nonnegative integers")
    if args.seeds and not args.web and not args.skip_compare and len(args.seeds) < 2:
        raise ValueError("A comparison needs at least two seeds")
    if sys.version_info < (3, 11):  # noqa: UP036 - bootstrap runs before package installation
        raise RuntimeError("Python 3.11+ is required; 3.12 is recommended")
    if not args.ready:
        python = bootstrap(args.tests)
        command = [
            str(python),
            str(Path(__file__).resolve()),
            "--ready",
            *(sys.argv[1:] if argv is None else argv),
        ]
        return subprocess.run(command, cwd=ROOT, check=False).returncode
    pipeline(args)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"\nSimroad launcher: {error}", file=sys.stderr)
        raise SystemExit(1)
