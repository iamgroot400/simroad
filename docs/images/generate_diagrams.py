"""Rebuild README PNG diagrams. Requires Pillow; run from any directory."""

from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BG = "#f5f3ec"
INK = "#253c36"
MUTED = "#596a65"
GREEN = "#177b63"
ORANGE = "#ba5d30"
BLUE = "#3c6f9a"


def font(size, bold=False):
    names = (
        ["C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
        if bold
        else ["C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default(size=size)


def canvas(height):
    image = Image.new("RGB", (1600, height), BG)
    return image, ImageDraw.Draw(image)


def text(draw, xy, value, size=28, color=INK, bold=False):
    draw.text(xy, value, font=font(size, bold), fill=color)


def arrow(draw, x1, y, x2):
    draw.line((x1, y, x2, y), fill=GREEN, width=5)
    draw.polygon([(x2, y), (x2 - 14, y - 9), (x2 - 14, y + 9)], fill=GREEN)


def workflow():
    image, draw = canvas(600)
    text(draw, (60, 38), "From a neighborhood to a repeatable experiment", 46, bold=True)
    text(
        draw,
        (60, 108),
        "You define the city and the question. SUMO simulates movement. Simroad compares outcomes.",
        27,
        MUTED,
    )
    columns = [
        (
            60,
            "1  Describe",
            ["Road map or offline grid", "Schools, offices and markets", "Vehicles, people and crossings"],
        ),
        (
            565,
            "2  Simulate",
            ["SUMO moves each traveler", "A policy controls signal timing", "Each run uses a recorded seed"],
        ),
        (
            1070,
            "3  Compare",
            [
                "Repeat policies on paired seeds",
                "Measure delay and throughput",
                "Check uncertainty and collisions",
            ],
        ),
    ]
    for x, title, lines in columns:
        draw.rounded_rectangle((x, 194, x + 465, 426), radius=18, fill="#ffffff", outline="#d2d9d2", width=2)
        draw.rectangle((x + 25, 222, x + 31, 258), fill=GREEN)
        text(draw, (x + 48, 216), title, 36, bold=True)
        for i, line in enumerate(lines):
            text(draw, (x + 25, 287 + i * 39), line, 25)
    arrow(draw, 529, 306, 555)
    arrow(draw, 1034, 306, 1060)
    draw.rounded_rectangle((60, 466, 1535, 554), radius=12, fill="#f7e6cb")
    text(draw, (83, 483), "Reality check", 28, ORANGE, True)
    text(
        draw,
        (280, 485),
        "Reports stay uncalibrated until matching field-count evidence passes validation.",
        27,
    )
    image.save(OUT / "simroad-workflow.png", optimize=True)


def neighborhood():
    network = ROOT / "runs/demo-network/network.net.xml"
    if not network.exists():
        raise SystemExit("Run simroad build --output runs/demo-network before rebuilding the network image")
    root = ET.parse(network).getroot()
    image, draw = canvas(960)
    text(draw, (60, 35), "The included neighborhood, explained", 46, bold=True)
    text(
        draw,
        (60, 103),
        "Actual offline-demo road geometry, with illustrative activity zones from config/zones.yaml.",
        27,
        MUTED,
    )
    left, top, scale = 80, 180, 1.15

    def xy(x, y):
        return left + x * scale + 25, top + (540 - y) * scale + 25

    draw.rounded_rectangle((60, 165, 785, 870), radius=18, fill="#e8ede5")
    # Zone centers/radii from the checked-in demo; verify when editing its configuration.
    zones = [
        (180, 180, 70, "#eec89c"),
        (360, 360, 80, "#b8cfe1"),
        (360, 180, 60, "#d2c4e0"),
        (180, 360, 70, "#b5d8c4"),
    ]
    for x, y, r, color in zones:
        a, b = xy(x, y)
        draw.ellipse((a - r * scale, b - r * scale, a + r * scale, b + r * scale), fill=color)
    for edge in root.findall("edge"):
        if edge.get("function") in ("internal", "walkingarea"):
            continue
        for lane in edge.findall("lane"):
            shape = [xy(*map(float, p.split(","))) for p in lane.get("shape", "").split()]
            if len(shape) < 2:
                continue
            if edge.get("function") == "crossing":
                color, width = "#fffdf5", 4
            elif lane.get("allow") == "pedestrian":
                color, width = "#afbbb0", 3
            else:
                color, width = "#61706b", 5
            draw.line(shape, fill=color, width=width)
    labels = [
        (180, 180, "School", -110, 35),
        (360, 360, "Offices", 20, -50),
        (360, 180, "Market", 15, 35),
        (180, 360, "Homes", -105, -50),
    ]
    for x, y, label, dx, dy in labels:
        a, b = xy(x, y)
        box = draw.textbbox((a + dx, b + dy), label, font=font(25, True))
        draw.rounded_rectangle((box[0] - 8, box[1] - 6, box[2] + 8, box[3] + 6), radius=5, fill=BG)
        text(draw, (a + dx, b + dy), label, 25, bold=True)
    # Junction identifiers match config/infrastructure.yaml.
    for x, y, label, color in [(180, 180, "A", ORANGE), (360, 180, "B", BLUE)]:
        a, b = xy(x, y)
        draw.ellipse((a - 18, b - 18, a + 18, b + 18), fill=color, outline=BG, width=3)
        text(draw, (a - 10, b - 18), label, 24, "white", True)
    text(draw, (835, 180), "Places create different demand", 33, bold=True)
    details = [
        ("School", "Arrival and pickup peaks; lower road speeds."),
        ("Offices", "Morning arrivals and evening departures."),
        ("Market", "Walking demand and reduced usable road width."),
        ("Homes", "Morning departures and evening returns."),
    ]
    for i, (name, desc) in enumerate(details):
        y = 245 + i * 100
        text(draw, (835, y), name, 29, bold=True)
        text(draw, (835, y + 39), desc, 25, MUTED)
    draw.line((835, 655, 1530, 655), fill="#c7cec4", width=2)
    text(draw, (835, 680), "A  Signalized crossing", 29, ORANGE, True)
    text(draw, (835, 722), "Walking follows the junction's signal phases.", 25)
    text(draw, (835, 775), "B  Zebra crossing", 29, BLUE, True)
    text(draw, (835, 817), "Pedestrians have priority; no signal cycle.", 25)
    text(
        draw,
        (60, 908),
        "Explanatory map, not a live screenshot. Zone colors and labels are documentation overlays.",
        24,
        MUTED,
    )
    image.save(OUT / "demo-neighborhood.png", optimize=True)


if __name__ == "__main__":
    workflow()
    neighborhood()
