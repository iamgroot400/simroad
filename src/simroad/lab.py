"""Paired-seed experiments; parallelize independent processes, never one SUMO instance."""

import statistics
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from scipy.stats import t

from .engine import run
from .report import write_report


def paired_comparison(baseline, candidate):
    if set(baseline) != set(candidate) or len(baseline) < 2:
        raise ValueError("A paired comparison needs identical sets of at least two seeds")
    if any(v is None for v in [*baseline.values(), *candidate.values()]):
        raise ValueError("Metric unavailable in at least one run; choose a metric defined for all seeds")
    differences = [candidate[s] - baseline[s] for s in sorted(baseline)]
    mean = statistics.mean(differences)
    margin = (
        float(t.ppf(0.975, len(differences) - 1)) * statistics.stdev(differences) / len(differences) ** 0.5
    )
    low, high = mean - margin, mean + margin
    return {
        "n_pairs": len(differences),
        "mean_candidate_minus_baseline": mean,
        "ci95": [low, high],
        "significant_95": bool(low > 0 or high < 0),
        "paired_differences": differences,
        "method": "Two-sided paired Student t interval; no multiplicity correction",
    }


def _task(args):
    bundle, network, output, seed, strategy, calibration = args
    return run(bundle, network, output, seed, strategy, calibration=calibration)


def compare(bundle, network, output, seeds, strategies, workers=1, calibration=None):
    if len(seeds) < 2 or len(set(seeds)) != len(seeds):
        raise ValueError("Provide at least two distinct seeds")
    if len(strategies) < 2 or len(set(strategies)) != len(strategies):
        raise ValueError("Provide at least two distinct strategies")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    jobs = [
        (bundle, str(network), str(output / f"{strategy}-seed-{seed}"), seed, strategy, calibration)
        for strategy in strategies
        for seed in seeds
    ]
    if workers == 1:
        runs = list(map(_task, jobs))
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            runs = list(pool.map(_task, jobs))
    baseline = strategies[0]
    comparisons = {}
    for candidate in strategies[1:]:
        # Ensure strategy changes did not alter the exogenous demand for a paired seed.
        for seed in seeds:
            paired = [r for r in runs if r["seed"] == seed and r["strategy"] in (baseline, candidate)]
            if len({r["demand_sha256"] for r in paired}) != 1:
                raise ValueError("Paired runs have different demand files")
        comparisons[candidate] = {}
        for metric in (
            "throughput_vehicles_per_hour",
            "total_stopped_vehicle_seconds",
            "collisions",
            "vehicles_unfinished",
        ):
            comparisons[candidate][metric] = paired_comparison(
                {r["seed"]: r[metric] for r in runs if r["strategy"] == baseline},
                {r["seed"]: r[metric] for r in runs if r["strategy"] == candidate},
            )
    data = {
        "baseline": baseline,
        "seeds": seeds,
        "comparisons": comparisons,
        "runs": runs,
        "interpretation": "Positive differences mean more of the metric; significance is not practical importance. Prefer >=10 seeds. Multiple endpoints are exploratory.",
    }
    return write_report(
        output / "comparison",
        "Simroad · paired scenario comparison",
        data,
        bundle.fingerprint(Path(network)),
        runs[0]["sumo_version"],
        calibration,
    )
