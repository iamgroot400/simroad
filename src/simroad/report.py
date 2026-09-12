"""One report path applies calibration provenance to every result."""

import html
import json
from pathlib import Path

UNCALIBRATED = "UNCALIBRATED — exploratory scenario comparison; not a validated real-world prediction."


def calibration_status(artifact, fingerprint, sumo_version):
    if artifact is None:
        return {"calibrated": False, "label": UNCALIBRATED}
    from .calibrate import evaluate

    try:
        data = json.loads(Path(artifact).read_text(encoding="utf-8"))
        validation = data["validation"]
        result = evaluate(validation["modeled_hourly"], validation["observed_hourly"])
        passed = (
            data["fingerprint"] == fingerprint
            and data["sumo_version"] == sumo_version
            and data["observations_kind"] == "field"
            and bool(data["observation_source"].strip())
            and set(data["fit_seeds"]).isdisjoint(data["validation_seeds"])
            and len(data["validation_seeds"]) >= 2
            and result["passed"]
        )
    except (KeyError, ValueError, TypeError, OSError):
        passed = False
    return {
        "calibrated": bool(passed),
        "label": (
            "FIELD-COUNT CALIBRATED — GEH passed for this configuration and observation window; other behaviors remain unvalidated."
            if passed
            else UNCALIBRATED
        ),
        "artifact": str(artifact),
    }


def write_report(path, title, data, fingerprint, sumo_version, calibration=None):
    path = Path(path)
    payload = {**data, "calibration": calibration_status(calibration, fingerprint, sumo_version)}
    path.with_suffix(".json").write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    rows = []
    for key, value in payload.items():
        if key == "calibration":
            continue
        formatted = (
            json.dumps(value, indent=2, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        )
        rows.append(
            f"<tr><th>{html.escape(key.replace('_', ' '))}</th><td><pre>{html.escape(formatted)}</pre></td></tr>"
        )
    path.with_suffix(".html").write_text(
        f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{html.escape(title)}</title><style>
body{{background:#f6f4ed;color:#26352f;font:16px/1.5 Georgia,serif;max-width:1100px;margin:40px auto;padding:0 24px}}
h1{{font-size:38px}}aside{{padding:18px;border:2px solid #ad642c;background:#fff1d8}}
table{{border-collapse:collapse;width:100%;margin-top:24px}}th,td{{text-align:left;vertical-align:top;padding:14px;border-bottom:1px solid #c8cec7}}
th{{width:26%}}pre{{font:13px/1.5 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;margin:0}}
</style><h1>{html.escape(title)}</h1><aside>{html.escape(payload["calibration"]["label"])}</aside>
<table>{"".join(rows)}</table><p>Simroad · Eclipse SUMO · Treat collisions, teleports and unfinished trips as model-health signals.</p></html>""",
        encoding="utf-8",
    )
    return payload
