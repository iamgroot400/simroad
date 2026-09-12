"""Spatial zone mapping and integrated, time-of-day trip generation."""

import itertools
import math


def pulse_mass(pulse, begin, end):
    """Fraction of a daily Gaussian pulse in [begin, end), normalized within that day."""
    mu, sd = pulse.hour * 3600, pulse.sigma_minutes * 60

    def cdf(t):
        return 0.5 * (1 + math.erf((t - mu) / (sd * math.sqrt(2))))

    return max(0, cdf(end) - cdf(begin)) / (cdf(86400) - cdf(0))


def expected_trips(zone, params, begin, end, mode, direction):
    rate = params.vehicle_trips_per_person if mode == "vehicle" else params.pedestrian_trips_per_person
    total_weight = sum(p.weight for p in params.pulses)
    return (
        zone.population
        * rate
        * sum(
            p.weight * pulse_mass(p, begin, end) / total_weight
            for p in params.pulses
            if p.direction == direction
        )
    )


def point_in_polygon(point, polygon):
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _distance_to_segment(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    denominator = dx * dx + dy * dy
    t = (
        0
        if denominator == 0
        else max(0, min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / denominator))
    )
    return math.hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy)


def map_zones(bundle, net):
    mapped = {}
    for zone in bundle.zones:
        if zone.edges:
            for edge in zone.edges:
                if not net.hasEdge(edge) or edge.startswith(":"):
                    raise ValueError(f"Zone {zone.id}: unknown edge {edge}")
            mapped[zone.id] = [net.getEdge(e) for e in zone.edges]
            continue
        convert = net.convertLonLat2XY if zone.coordinates == "lonlat" else lambda x, y: (x, y)
        if zone.coordinates == "lonlat" and not net.hasGeoProj():
            raise ValueError(f"Zone {zone.id} uses lonlat on a network without geographic projection")
        center = convert(*zone.center) if zone.center else None
        polygon = [convert(*p) for p in zone.polygon] if zone.polygon else None
        selected = []
        for edge in net.getEdges():
            if edge.getID().startswith(":"):
                continue
            shape = edge.getShape()
            if center:
                hit = any(
                    _distance_to_segment(center, a, b) <= zone.radius_m for a, b in itertools.pairwise(shape)
                )
            else:
                # Densification also catches long road segments passing through the polygon.
                samples = []
                for a, b in itertools.pairwise(shape):
                    steps = max(1, math.ceil(math.dist(a, b) / 5))
                    samples.extend(
                        (a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps)
                        for i in range(steps + 1)
                    )
                hit = any(point_in_polygon(p, polygon) for p in samples)
            if hit:
                selected.append(edge)
        if not selected:
            raise ValueError(
                f"Zone {zone.id} intersects no edges. Check coordinates or supply explicit edges."
            )
        mapped[zone.id] = selected
    return mapped
