import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "run_all", Path(__file__).resolve().parents[1] / "scripts/run_all.py"
)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_reuses_healthy_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    python = launcher.env_python(tmp_path / ".venv")
    python.parent.mkdir(parents=True)
    python.touch()
    monkeypatch.setattr(launcher, "healthy", lambda *args: True)
    monkeypatch.setattr(
        launcher, "execute", lambda cmd: pytest.fail("Must not recreate a healthy environment")
    )
    assert launcher.bootstrap() == python


def test_preserves_broken_environments(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    for name in (".venv", ".venv-runner"):
        python = launcher.env_python(tmp_path / name)
        python.parent.mkdir(parents=True)
        python.write_text("existing executable")
    monkeypatch.setattr(launcher, "healthy", lambda python, tests=False: ".venv-runner-" in str(python))
    commands = []
    monkeypatch.setattr(launcher, "execute", commands.append)
    result = launcher.bootstrap()
    assert result.is_relative_to(tmp_path)
    assert ".venv-runner-" in str(result)
    assert commands[0][1:3] == ["-m", "venv"]
    assert len(commands) == 2
    assert launcher.env_python(tmp_path / ".venv").read_text() == "existing executable"


def test_child_failure_is_returned(monkeypatch):
    monkeypatch.setattr(launcher, "bootstrap", lambda tests: Path("python"))
    monkeypatch.setattr(launcher.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=7))
    assert launcher.main(["--quick", "--no-open"]) == 7


def test_invalid_seeds_fail_before_setup(monkeypatch):
    monkeypatch.setattr(launcher, "bootstrap", lambda tests: pytest.fail("Should not bootstrap"))
    with pytest.raises(ValueError, match="at least two"):
        launcher.main(["--batch", "--seeds", "1"])


def test_default_browser_and_explicit_batch_commands(tmp_path, monkeypatch):
    project = launcher.ROOT / "config/project.yaml"
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    commands = []
    opened = []
    monkeypatch.setattr(launcher, "execute", commands.append)
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: opened.append(url))
    launcher.pipeline(launcher.arguments(["--project", str(project)]))
    serve = commands[-1]
    assert "serve" in serve
    assert "--no-open" not in serve
    assert not opened  # The serve command opens the browser after binding its socket.
    commands.clear()
    launcher.pipeline(launcher.arguments(["--project", str(project), "--no-open"]))
    assert "serve" in commands[-1] and "--no-open" in commands[-1]
    commands.clear()
    launcher.pipeline(launcher.arguments(["--project", str(project), "--batch", "--skip-compare"]))
    assert "run" in commands[-1]
    assert len(opened) == 1 and opened[0].endswith("report.html")
