from . import register


@register("fixed")
class Fixed:
    """SUMO signal programs with a shared mandatory pedestrian service floor."""

    def __init__(self, connection, bundle):
        self.c = connection
        self.sim = bundle.project.simulation
        self.floor = {}
        self.crossings = {}
        # Conservatively apply the most protective active zone to every crossing.
        # This deliberately over-services distant crossings rather than missing a hospital floor.
        walk_floor = max((p.min_walk_seconds for p in bundle.parameters.values()), default=10)
        walk_speed = min((p.pedestrian_speed for p in bundle.parameters.values()), default=1.2)
        for tls in connection.trafficlight.getIDList():
            programs = connection.trafficlight.getAllProgramLogics(tls)
            active = connection.trafficlight.getProgram(tls)
            logic = next(p for p in programs if p.programID == active)
            links = connection.trafficlight.getControlledLinks(tls)
            crossing_indices = {}
            for i, group in enumerate(links):
                for source, target, via in group:
                    for lane in (source, target, via):
                        if (
                            lane
                            and "_c" in connection.lane.getEdgeID(lane)
                            and connection.lane.getEdgeID(lane).startswith(":")
                        ):
                            crossing_indices[i] = lane
            local_floor = max(
                [walk_floor] + [c.min_walk_seconds for c in bundle.infrastructure.crossings if c.node == tls]
            )
            for index, phase in enumerate(logic.phases):
                green_crossings = [lane for i, lane in crossing_indices.items() if phase.state[i] in "gG"]
                floor = (
                    max(
                        [self.sim.min_green]
                        + [
                            local_floor,
                            *[connection.lane.getLength(lane) / walk_speed for lane in green_crossings],
                        ]
                    )
                    if green_crossings
                    else self.sim.min_green
                )
                if "y" in phase.state.lower() or not any(c in "gG" for c in phase.state):
                    floor = phase.duration  # Never shorten yellow/all-red clearance.
                phase.duration = max(phase.duration, floor)
                phase.minDur = phase.duration
                phase.maxDur = phase.duration
                self.floor[tls, index] = floor
            logic.type = 0
            connection.trafficlight.setProgramLogic(tls, logic)
            connection.trafficlight.setProgram(tls, logic.programID)
            self.crossings[tls] = crossing_indices

    def step(self):
        pass
