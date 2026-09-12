"""SUMO owns car following, lane changing and junction physics."""

import xml.etree.ElementTree as ET

from .config import Fleet


def add_types(root: ET.Element, fleet: Fleet):
    for t in fleet.types:
        ET.SubElement(
            root,
            "vType",
            {
                k: str(v)
                for k, v in {
                    "id": t.id,
                    "vClass": t.vclass,
                    "length": t.length,
                    "width": t.width,
                    "maxSpeed": t.max_speed,
                    "accel": t.accel,
                    "decel": t.decel,
                    "tau": t.tau,
                    "sigma": t.sigma,
                    "speedDev": t.speed_deviation,
                    "minGap": t.min_gap,
                    "minGapLat": t.min_gap_lat,
                    "lcAssertive": t.lc_assertive,
                    "lcPushy": t.lc_pushy,
                    "lcSpeedGain": t.lc_speed_gain,
                    "jmDriveAfterYellowTime": t.jm_drive_after_yellow,
                    "jmDriveAfterRedTime": t.jm_drive_after_red,
                    "jmIgnoreFoeProb": t.jm_ignore_foe_probability,
                    "laneChangeModel": "SL2015",
                    "carFollowModel": "Krauss",
                }.items()
            },
        )


def write_xml(root, path):
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
