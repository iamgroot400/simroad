"""Explicit grid fitting with held-out random seeds and GEH validation."""

import csv
import hashlib
import itertools
import json
import math
import statistics
from copy import deepcopy
from pathlib import Path

import sumolib

from .engine import run
from .report import write_report


def geh(modeled, observed):
    if not math.isfinite(modeled) or not math.isfinite(observed) or modeled < 0 or observed < 0:
        raise ValueError("GEH requires finite nonnegative hourly flows")
    return math.sqrt(2 * (modeled - observed) ** 2 / (modeled + observed)) if modeled + observed else 0.0


def evaluate(modeled, observed):
    if not modeled or set(modeled) != set(observed):
        raise ValueError("Calibration needs matching nonempty detector IDs")
    values = {key: geh(modeled[key], observed[key]) for key in observed}
    fraction = sum(value < 5 for value in values.values()) / len(values)
    return {
        "geh": values,
        "fraction_below_5": fraction,
        "passed": fraction >= 0.85 and all(value < 10 for value in values.values()),
    }


def apply_parameters(bundle, parameters):
    tuned = deepcopy(bundle)
    tuned.demand.scale *= parameters["demand_scale"]
    for vehicle_type in tuned.fleet.types:
        vehicle_type.tau *= parameters["tau_scale"]
    share = parameters.get("motorcycle_share")
    if share is not None:
        motorcycles = [v for v in tuned.fleet.types if v.vclass == "motorcycle"]
        others = [v for v in tuned.fleet.types if v.vclass != "motorcycle"]
        old_m, old_o = sum(v.share for v in motorcycles), sum(v.share for v in others)
        if not 0 <= share <= 1 or old_m <= 0 or old_o <= 0:
            raise ValueError(
                "Motorcycle fitting needs positive original motorcycle and non-motorcycle shares"
            )
        for v in motorcycles:
            v.share = v.share / old_m * share
        for v in others:
            v.share = v.share / old_o * (1 - share)
    tuned.validate()
    return tuned


def calibrate(
    bundle,
    network,
    output,
    observations,
    source,
    kind,
    demand_scales,
    tau_scales,
    motorcycle_shares,
    fit_seeds,
    validation_seeds,
):
    if (
        not source.strip()
        or len(fit_seeds) < 2
        or len(validation_seeds) < 2
        or set(fit_seeds) & set(validation_seeds)
        or len(set(fit_seeds)) != len(fit_seeds)
        or len(set(validation_seeds)) != len(validation_seeds)
    ):
        raise ValueError(
            "Supply observation provenance and two or more distinct seeds in each disjoint seed set"
        )
    if any(not math.isfinite(v) or v <= 0 for v in demand_scales + tau_scales):
        raise ValueError("Calibration multipliers must be finite and positive")
    sim = bundle.project.simulation
    net = sumolib.net.readNet(str(network))
    observed = {}
    with Path(observations).open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            edge, count = row["edge"], float(row["count"])
            if edge in observed or not net.hasEdge(edge) or not math.isfinite(count) or count < 0:
                raise ValueError("Observed edges must be unique and present, with finite nonnegative counts")
            if float(row["begin"]) != sim.begin or float(row["end"]) != sim.end:
                raise ValueError("Observation windows must exactly match the configured simulation window")
            observed[edge] = count * 3600 / (sim.end - sim.begin)
    if not observed:
        raise ValueError("Observation CSV is empty")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)

    def measure(model, prefix, seeds):
        runs = [run(model, network, output / f"{prefix}-{seed}", seed) for seed in seeds]
        counts = {
            e: statistics.mean(r["edge_counts"].get(e, 0) for r in runs) * 3600 / (sim.end - sim.begin)
            for e in observed
        }
        return counts, runs[0]["sumo_version"]

    candidates = []
    for i, (d, tau, mix) in enumerate(itertools.product(demand_scales, tau_scales, motorcycle_shares)):
        parameters = {"demand_scale": d, "tau_scale": tau, "motorcycle_share": mix}
        tuned = apply_parameters(bundle, parameters)
        modeled, _ = measure(tuned, f"candidate-{i}", fit_seeds)
        goodness = evaluate(modeled, observed)
        candidates.append(
            {"parameters": parameters, "score": statistics.mean(goodness["geh"].values()), "fit": goodness}
        )
    best = min(candidates, key=lambda c: c["score"])
    tuned = apply_parameters(bundle, best["parameters"])
    modeled, version = measure(tuned, "validation", validation_seeds)
    validation = {"modeled_hourly": modeled, "observed_hourly": observed, **evaluate(modeled, observed)}
    artifact = {
        "fingerprint": tuned.fingerprint(Path(network)),
        "sumo_version": version,
        "base_fingerprint": bundle.fingerprint(Path(network)),
        "parameters": best["parameters"],
        "observations_kind": kind,
        "observation_source": source,
        "observation_sha256": hashlib.sha256(Path(observations).read_bytes()).hexdigest(),
        "fit_seeds": fit_seeds,
        "validation_seeds": validation_seeds,
        "validation": validation,
        "candidates": candidates,
        "scope": "Fits hourly edge-entry counts, not safety or travel times. Validation seeds are held out; observations are not held-out sites.",
    }
    artifact_path = output / "calibration.json"
    artifact_path.write_text(json.dumps(artifact, indent=2, allow_nan=False), encoding="utf-8")
    return write_report(
        output / "report", "Simroad · calibration", artifact, artifact["fingerprint"], version, artifact_path
    )
