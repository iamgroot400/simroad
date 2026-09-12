"""Validated configuration; all relative paths resolve against the project YAML."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class City(Model):
    source: Literal["demo", "osm", "network"] = "demo"
    bbox: tuple[float, float, float, float] | None = None  # west, south, east, north
    place: str | None = None
    osm_file: str | None = None
    network_file: str | None = None
    left_hand: bool = False
    grid_size: int = Field(4, ge=3, le=20)
    grid_length_m: float = Field(180, gt=50)
    overpass_url: str = "https://overpass-api.de/api/interpreter"

    @model_validator(mode="after")
    def source_valid(self):
        if self.source == "osm" and not (self.bbox or self.place or self.osm_file):
            raise ValueError("OSM requires bbox, place, or osm_file")
        if self.source == "network" and not self.network_file:
            raise ValueError("network source requires network_file")
        if self.bbox:
            w, s, e, n = self.bbox
            if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
                raise ValueError("bbox must be [west, south, east, north], without antimeridian wrapping")
        return self


class FleetType(Model):
    id: str
    vclass: str
    share: float = Field(ge=0, le=1)
    length: float = Field(gt=0)
    width: float = Field(gt=0)
    max_speed: float = Field(gt=0)
    accel: float = Field(gt=0)
    decel: float = Field(gt=0)
    tau: float = Field(gt=0)
    sigma: float = Field(ge=0, le=1)
    speed_deviation: float = Field(ge=0)
    min_gap: float = Field(ge=0)
    min_gap_lat: float = Field(ge=0)
    lc_assertive: float = Field(gt=0)
    lc_pushy: float = Field(ge=0, le=1)
    lc_speed_gain: float = Field(ge=0)
    jm_drive_after_yellow: float = Field(ge=0)
    jm_drive_after_red: float = Field(ge=0)
    jm_ignore_foe_probability: float = Field(ge=0, le=1)


class Fleet(Model):
    name: str
    description: str
    types: list[FleetType] = Field(min_length=1)

    @model_validator(mode="after")
    def shares_valid(self):
        if abs(sum(t.share for t in self.types) - 1) > 1e-6:
            raise ValueError("Fleet shares must sum to 1")
        if len({t.id for t in self.types}) != len(self.types):
            raise ValueError("Fleet type IDs must be unique")
        return self


class Pulse(Model):
    hour: float = Field(ge=0, lt=24)
    sigma_minutes: float = Field(gt=0)
    weight: float = Field(gt=0)
    direction: Literal["in", "out"] = "in"


class ZoneParameters(Model):
    vehicle_trips_per_person: float = Field(ge=0)
    pedestrian_trips_per_person: float = Field(ge=0)
    speed_kph: float | None = Field(None, gt=0)
    encroachment_fraction: float = Field(0, ge=0, lt=0.8)
    min_walk_seconds: float = Field(10, gt=0)
    pedestrian_speed: float = Field(1.2, gt=0)
    informal_crossing_probability: float = Field(0, ge=0, le=1)
    parking_search_probability: float = Field(0, ge=0, le=1)
    parking_search_seconds: float = Field(30, ge=0)
    pulses: list[Pulse] = Field(min_length=1)


class Zone(Model):
    id: str
    type: Literal["school", "office", "market", "residential", "hospital", "transit"]
    population: int = Field(gt=0)
    coordinates: Literal["xy", "lonlat"] = "lonlat"
    center: tuple[float, float] | None = None
    radius_m: float = Field(100, gt=0)
    polygon: list[tuple[float, float]] | None = Field(None, min_length=3)
    edges: list[str] = Field(default_factory=list)
    parameters: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def geometry_valid(self):
        if not self.edges and (self.center is None) == (self.polygon is None):
            raise ValueError("Zone needs explicit edges, or exactly one center/polygon")
        return self


class Gateway(Model):
    edge: str
    to_edge: str
    vehicles_per_hour: float = Field(ge=0)
    begin_hour: float = Field(0, ge=0, lt=24)
    end_hour: float = Field(24, gt=0, le=24)

    @model_validator(mode="after")
    def time_valid(self):
        if self.end_hour <= self.begin_hour:
            raise ValueError("Gateway end_hour must exceed begin_hour")
        return self


class Demand(Model):
    derive_from_zones: bool = True
    scale: float = Field(1, gt=0)
    bin_minutes: float = Field(5, gt=0, le=60)
    gateways: list[Gateway] = Field(default_factory=list)


class Crossing(Model):
    node: str
    edges: list[str] = Field(min_length=1)
    kind: Literal["signalized", "zebra", "informal"]
    width_m: float = Field(4, gt=0)
    min_walk_seconds: float = Field(10, gt=0)


class TransitStop(Model):
    id: str
    lane: str
    start_pos: float = Field(ge=0)
    end_pos: float = Field(gt=0)
    blocks_lane: bool = True
    dwell_mean: float = Field(20, ge=0)
    dwell_std: float = Field(5, ge=0)
    stop_probability: float = Field(1, ge=0, le=1)


class TransitRoute(Model):
    id: str
    type: str
    edges: list[str] = Field(min_length=2)
    stops: list[str]
    headway_seconds: float = Field(600, gt=0)


class Infrastructure(Model):
    crossings: list[Crossing] = Field(default_factory=list)
    stops: list[TransitStop] = Field(default_factory=list)
    transit_routes: list[TransitRoute] = Field(default_factory=list)


class Simulation(Model):
    begin: float = Field(25200, ge=0)
    end: float = Field(32400, gt=0, le=86400)
    step_length: float = Field(0.2, gt=0)
    lateral_resolution: float = Field(0.4, gt=0)
    min_green: float = Field(10, gt=0)
    max_green: float = Field(60, gt=0)

    @model_validator(mode="after")
    def times_valid(self):
        if self.end <= self.begin or self.max_green < self.min_green:
            raise ValueError("Require end > begin and max_green >= min_green")
        return self


class Project(Model):
    name: str
    city: str = "city.yaml"
    zones: str = "zones.yaml"
    zone_defaults: str = "zone_defaults.yaml"
    fleet: str = "fleet_profiles/mixed_motorcycle.yaml"
    demand: str = "demand.yaml"
    infrastructure: str = "infrastructure.yaml"
    simulation: Simulation = Field(default_factory=Simulation)


def read_yaml(path: Path):
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


class Bundle:
    def __init__(self, path: str | Path, fleet_override: str | None = None):
        self.path = Path(path).resolve()
        self.root = self.path.parent
        self.project = Project.model_validate(read_yaml(self.path))
        if fleet_override:
            self.project.fleet = str(Path(fleet_override).resolve())
        self.city = City.model_validate(read_yaml(self.resolve(self.project.city)))
        self.fleet = Fleet.model_validate(read_yaml(self.resolve(self.project.fleet)))
        self.zones = [Zone.model_validate(z) for z in read_yaml(self.resolve(self.project.zones))["zones"]]
        if len({z.id for z in self.zones}) != len(self.zones):
            raise ValueError("Zone IDs must be unique")
        defaults = read_yaml(self.resolve(self.project.zone_defaults))
        self.parameters = {
            z.id: ZoneParameters.model_validate({**defaults[z.type], **z.parameters}) for z in self.zones
        }
        self.demand = Demand.model_validate(read_yaml(self.resolve(self.project.demand)))
        self.infrastructure = Infrastructure.model_validate(
            read_yaml(self.resolve(self.project.infrastructure))
        )
        self.validate()

    def resolve(self, path):
        return (self.root / path).resolve()

    def validate(self):
        transit_types = {r.type for r in self.infrastructure.transit_routes}
        tau = min(t.tau for t in self.fleet.types if t.share > 0 or t.id in transit_types)
        if self.project.simulation.step_length > tau:
            raise ValueError(f"step_length must be <= shortest active tau ({tau}s)")

    def fingerprint(self, network: Path):
        payload = {
            "project": self.project.model_dump(
                exclude={"city", "zones", "zone_defaults", "fleet", "demand", "infrastructure"}
            ),
            "city": self.city.model_dump(),
            "fleet": self.fleet.model_dump(),
            "zones": [z.model_dump() for z in self.zones],
            "parameters": {k: v.model_dump() for k, v in self.parameters.items()},
            "demand": self.demand.model_dump(),
            "infrastructure": self.infrastructure.model_dump(),
            "network_sha256": hashlib.sha256(network.read_bytes()).hexdigest(),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def network_fingerprint(self):
        """Inputs affecting constructed geometry, permissions, speed or width."""
        payload = {
            "city": self.city.model_dump(),
            "zones": [z.model_dump() for z in self.zones],
            "parameters": {k: v.model_dump() for k, v in self.parameters.items()},
            "crossings": [c.model_dump() for c in self.infrastructure.crossings],
        }
        for attr in ("osm_file", "network_file"):
            source = getattr(self.city, attr)
            if source:
                payload[attr + "_sha256"] = hashlib.sha256(self.resolve(source).read_bytes()).hexdigest()
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
