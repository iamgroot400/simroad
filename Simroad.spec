from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata


root = Path(SPEC).resolve().parent
datas = [
    (str(root / "config"), "config"),
    (str(root / "examples" / "kathmandu_major_roads"), "examples/kathmandu_major_roads"),
    (
        str(root / "build" / "desktop-studio-network" / "network.net.xml"),
        "network/studio",
    ),
    (
        str(root / "build" / "desktop-kathmandu-network" / "network.net.xml"),
        "network/kathmandu",
    ),
    (str(root / "packaging" / "README-DOWNLOAD.txt"), "."),
]
binaries = []
hiddenimports = []

for package in ("sumo", "sumolib", "traci", "rtree"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

datas += collect_data_files("simroad")
for distribution in ("eclipse-sumo", "sumolib", "traci", "rtree"):
    datas += copy_metadata(distribution)

analysis = Analysis(
    [str(root / "scripts" / "desktop.py")],
    pathex=[str(root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
archive = PYZ(analysis.pure)
studio_executable = EXE(
    archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Simroad-Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
studio_bundle = COLLECT(
    studio_executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Simroad-Studio",
)
kathmandu_executable = EXE(
    archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Simroad-Kathmandu",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
kathmandu_bundle = COLLECT(
    kathmandu_executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Simroad-Kathmandu",
)
