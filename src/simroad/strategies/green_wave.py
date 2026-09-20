"""Coordinate signal offsets along the network's dominant geographic axis."""

from . import register
from .fixed import Fixed


@register("green_wave")
class GreenWave(Fixed):
    """Offset fixed programs for a 40 km/h progression speed."""

    SPEED_METERS_PER_SECOND = 40 / 3.6

    def __init__(self, connection, bundle):
        super().__init__(connection, bundle)
        signals = list(connection.trafficlight.getIDList())
        if not signals:
            return
        positions = {tls: connection.junction.getPosition(tls) for tls in signals}
        x_range = max(point[0] for point in positions.values()) - min(
            point[0] for point in positions.values()
        )
        y_range = max(point[1] for point in positions.values()) - min(
            point[1] for point in positions.values()
        )
        axis = 0 if x_range >= y_range else 1
        origin = min(point[axis] for point in positions.values())
        now = connection.simulation.getTime()
        for tls in signals:
            active = connection.trafficlight.getProgram(tls)
            logic = next(
                item
                for item in connection.trafficlight.getAllProgramLogics(tls)
                if item.programID == active
            )
            cycle = sum(phase.duration for phase in logic.phases)
            if not cycle:
                continue
            travel_offset = (positions[tls][axis] - origin) / self.SPEED_METERS_PER_SECOND
            elapsed = (now - bundle.project.simulation.begin - travel_offset) % cycle
            cumulative = 0.0
            for index, phase in enumerate(logic.phases):
                if elapsed < cumulative + phase.duration:
                    connection.trafficlight.setPhase(tls, index)
                    connection.trafficlight.setPhaseDuration(
                        tls, max(bundle.project.simulation.step_length, cumulative + phase.duration - elapsed)
                    )
                    break
                cumulative += phase.duration

    def step(self):
        pass
