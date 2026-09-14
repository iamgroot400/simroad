"""Bounded browser calibration inputs; field provenance is never inferred."""

import csv
import io
import math
from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..config import Model

Seed = Annotated[int, Field(strict=True, ge=0, le=2147483647)]
Multiplier = Annotated[float, Field(gt=0, le=10)]


class CalibrationJob(Model):
    observations: str = Field(min_length=1, max_length=1000000)
    source: str = Field(min_length=1, max_length=2000)
    kind: Literal["field", "synthetic"]
    demand_scales: list[Multiplier] = Field(
        default_factory=lambda: [0.75, 1, 1.25], min_length=1, max_length=6
    )
    tau_scales: list[Multiplier] = Field(default_factory=lambda: [1], min_length=1, max_length=6)
    fit_seeds: list[Seed] = Field(default_factory=lambda: [101, 102], min_length=2, max_length=5)
    validation_seeds: list[Seed] = Field(default_factory=lambda: [201, 202], min_length=2, max_length=5)

    @model_validator(mode="after")
    def validate_batch(self):
        if not self.source.strip():
            raise ValueError("Describe the observation source, date and counting method")
        if (
            len(set(self.fit_seeds)) != len(self.fit_seeds)
            or len(set(self.validation_seeds)) != len(self.validation_seeds)
            or set(self.fit_seeds) & set(self.validation_seeds)
        ):
            raise ValueError("Use distinct, disjoint fitting and validation seeds")
        if len(self.demand_scales) * len(self.tau_scales) > 12:
            raise ValueError("The browser supports at most 12 parameter combinations per batch")
        return self

    def validate_counts(self, bundle, net):
        reader = csv.DictReader(io.StringIO(self.observations.lstrip("\ufeff")))
        if reader.fieldnames != ["edge", "count", "begin", "end"]:
            raise ValueError("CSV header must be edge,count,begin,end")
        seen = set()
        sim = bundle.project.simulation
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError("Every CSV row needs four columns")
            edge = row["edge"]
            try:
                count, begin, end = (float(row[k]) for k in ("count", "begin", "end"))
            except ValueError as error:
                raise ValueError("CSV count and time values must be numeric") from error
            if (
                edge in seen
                or not net.hasEdge(edge)
                or not net.getEdge(edge).allows("passenger")
                or not math.isfinite(count)
                or count < 0
            ):
                raise ValueError("Use unique vehicle edge IDs with finite, nonnegative counts")
            if begin != sim.begin or end != sim.end:
                raise ValueError(f"Observation window must be {sim.begin} to {sim.end} simulation seconds")
            seen.add(edge)
        if not seen:
            raise ValueError("Add at least one observed count row")
