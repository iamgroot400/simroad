"""Entry point shared by the self-contained Simroad desktop editions."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import sumolib

from simroad.config import Bundle
from simroad.live_view.server import serve
from simroad.osm_import import binary, prepare_network
from simroad.strategies import available


def resource_root():
    """Return bundled resources under PyInstaller or the repository in development."""
    frozen = getattr(sys, "_MEIPASS", None)
    return Path(frozen) if frozen else Path(__file__).resolve().parents[1]


def user_data_root():
    """Use a writable, per-user output directory on each desktop platform."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "Simroad"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Simroad"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "simroad"


def edition_from_executable(executable=None):
    """Select the packaged edition from its executable name."""
    name = Path(executable or sys.executable).stem.lower()
    return "studio" if "studio" in name else "kathmandu"


def arguments(argv=None, executable=None):
    default_edition = edition_from_executable(executable)
    parser = argparse.ArgumentParser(description="Launch a local Simroad desktop edition")
    parser.add_argument("--port", type=int, default=8765, help="Local-only viewer port")
    parser.add_argument("--no-open", action="store_true", help="Do not open the browser automatically")
    parser.add_argument(
        "--edition",
        choices=("studio", "kathmandu"),
        default=default_edition,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def project_path(root, edition):
    if edition == "studio":
        return root / "config" / "project.yaml"
    return root / "examples" / "kathmandu_major_roads" / "project.yaml"


def bundled_network(root, bundle, output, edition):
    packaged = root / "network" / edition / "network.net.xml"
    if packaged.is_file():
        return packaged
    label = "editable starter city" if edition == "studio" else "Kathmandu Valley road map"
    print(f"Preparing the included {label} for first launch...", flush=True)
    return prepare_network(bundle, output / "network")


def smoke_test(bundle, network, edition):
    net = sumolib.net.readNet(str(network))
    if not net.getEdges():
        raise RuntimeError(f"The bundled {edition} network has no roads")
    policies = set(available())
    required = {"fixed", "pressure", "webster", "green_wave"}
    if missing := required - policies:
        raise RuntimeError(f"The desktop package is missing signal policies: {', '.join(sorted(missing))}")
    result = subprocess.run(
        [binary("sumo"), "--version"], capture_output=True, text=True, check=False, timeout=30
    )
    if result.returncode:
        raise RuntimeError("The bundled SUMO engine could not start")
    print(
        f"Simroad {edition.title()} smoke test passed: {len(net.getEdges())} road edges; "
        f"policies: {', '.join(sorted(policies))}"
    )


def main(argv=None, executable=None):
    args = arguments(argv, executable)
    if not 0 <= args.port <= 65535:
        raise ValueError("Port must be between 0 and 65535")
    root = resource_root()
    project = project_path(root, args.edition)
    if not project.is_file():
        raise RuntimeError(f"Bundled {args.edition} project is missing: {project}")
    bundle = Bundle(project)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    output = user_data_root() / args.edition / "runs" / ("desktop-" + stamp)
    output.mkdir(parents=True, exist_ok=False)
    network = bundled_network(root, bundle, output, args.edition)
    if args.smoke_test:
        smoke_test(bundle, network, args.edition)
        return 0
    label = "Studio" if args.edition == "studio" else "Kathmandu"
    print(f"Simroad {label} runs entirely on this computer.", flush=True)
    print("The viewer is available only on 127.0.0.1 and is not exposed to the network.", flush=True)
    print(f"Run files: {output}", flush=True)
    serve(bundle, network, output, port=args.port, open_browser=not args.no_open)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Simroad desktop: {error}", file=sys.stderr)
        if sys.platform == "win32" and sys.stdin.isatty():
            input("Press Enter to close...")
        raise SystemExit(1)
