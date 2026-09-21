from pathlib import Path

from scripts import desktop


def test_desktop_edition_is_selected_from_executable_name():
    assert desktop.edition_from_executable("Simroad-Studio.exe") == "studio"
    assert desktop.edition_from_executable("Simroad-Kathmandu.exe") == "kathmandu"
    assert desktop.edition_from_executable("Simroad.exe") == "kathmandu"


def test_desktop_editions_use_distinct_projects_and_networks(tmp_path):
    root = Path.cwd()
    studio = desktop.arguments([], executable="Simroad-Studio.exe")
    kathmandu = desktop.arguments([], executable="Simroad-Kathmandu.exe")

    assert studio.edition == "studio"
    assert kathmandu.edition == "kathmandu"
    assert desktop.project_path(root, studio.edition) == root / "config" / "project.yaml"
    assert desktop.project_path(root, kathmandu.edition) == (
        root / "examples" / "kathmandu_major_roads" / "project.yaml"
    )
    assert (tmp_path / "network" / studio.edition) != (
        tmp_path / "network" / kathmandu.edition
    )
