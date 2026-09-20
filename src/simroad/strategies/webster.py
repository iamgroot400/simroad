"""Queue-adaptive signal timing based on Webster cycle and split principles."""

from . import register
from .fixed import Fixed


@register("webster")
class AdaptiveWebster(Fixed):
    """Recalculate bounded green splits when each green phase begins."""

    def __init__(self, connection, bundle):
        super().__init__(connection, bundle)
        self.previous_phase = {}
        self.logic = {}
        for tls in connection.trafficlight.getIDList():
            active = connection.trafficlight.getProgram(tls)
            self.logic[tls] = next(
                logic
                for logic in connection.trafficlight.getAllProgramLogics(tls)
                if logic.programID == active
            )

    def step(self):
        for tls in self.c.trafficlight.getIDList():
            phase_index = self.c.trafficlight.getPhase(tls)
            if self.previous_phase.get(tls) == phase_index:
                continue
            self.previous_phase[tls] = phase_index
            state = self.c.trafficlight.getRedYellowGreenState(tls)
            if "y" in state.lower() or not any(value in "gG" for value in state):
                continue

            links = self.c.trafficlight.getControlledLinks(tls)
            green = {
                source for i, group in enumerate(links) if state[i] in "gG" for source, _, _ in group
            }
            approaches = {source for group in links for source, _, _ in group}
            demand = {
                lane: self.c.lane.getLastStepHaltingNumber(lane)
                + 0.25 * self.c.lane.getLastStepVehicleNumber(lane)
                for lane in approaches
            }
            green_demand = sum(demand.get(lane, 0) for lane in green)
            total_demand = sum(demand.values())
            logic = self.logic[tls]
            lost_time = sum(
                phase.duration
                for phase in logic.phases
                if "y" in phase.state.lower() or not any(value in "gG" for value in phase.state)
            )
            capacity_proxy = max(1.0, len(approaches) * 20.0)
            critical_ratio = min(0.9, total_demand / capacity_proxy)
            cycle = (1.5 * lost_time + 5) / max(0.1, 1 - critical_ratio)
            effective_green = max(self.sim.min_green, cycle - lost_time)
            share = green_demand / total_demand if total_demand else 1 / max(1, len(logic.phases))
            duration = max(
                self.floor[tls, phase_index],
                min(self.sim.max_green, effective_green * share),
            )
            self.c.trafficlight.setPhaseDuration(tls, duration)
