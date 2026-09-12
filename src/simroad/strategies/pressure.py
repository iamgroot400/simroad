import traci.constants as tc

from . import register
from .fixed import Fixed


@register("pressure")
class Pressure(Fixed):
    """Extend a demanded green, or release an empty one, without skipping clearance phases."""

    def step(self):
        c = self.c
        for person in c.simulation.getDepartedPersonIDList():
            c.person.subscribe(person, [tc.VAR_WAITING_TIME, tc.VAR_NEXT_EDGE])
        for tls in c.trafficlight.getIDList():
            state = c.trafficlight.getRedYellowGreenState(tls)
            if "y" in state.lower() or not any(s in "gG" for s in state):
                continue
            phase = c.trafficlight.getPhase(tls)
            elapsed = c.trafficlight.getSpentDuration(tls)
            floor = self.floor[tls, phase]
            if elapsed < floor:
                continue
            links = c.trafficlight.getControlledLinks(tls)
            green_lanes = {
                source for i, group in enumerate(links) if state[i] in "gG" for source, _, _ in group
            }
            red_lanes = {
                source for i, group in enumerate(links) if state[i] in "rR" for source, _, _ in group
            }
            green_demand = sum(c.lane.getLastStepHaltingNumber(lane) for lane in green_lanes)
            red_demand = sum(c.lane.getLastStepHaltingNumber(lane) for lane in red_lanes)
            # A waiting person's next crossing requests service, like a crossing button.
            waiting_crossings = {
                values[tc.VAR_NEXT_EDGE]
                for values in c.person.getAllSubscriptionResults().values()
                if values[tc.VAR_WAITING_TIME] > 0
            }
            pedestrian_request = any(
                c.lane.getEdgeID(lane) in waiting_crossings and state[i] in "rR"
                for i, lane in self.crossings[tls].items()
            )
            remaining = c.trafficlight.getNextSwitch(tls) - c.simulation.getTime()
            if (
                elapsed >= max(self.sim.max_green, floor)
                or pedestrian_request
                or (not green_demand and red_demand)
            ):
                c.trafficlight.setPhaseDuration(tls, min(remaining, self.sim.step_length))
            elif green_demand and remaining <= self.sim.step_length * 2:
                c.trafficlight.setPhaseDuration(tls, min(2, max(self.sim.max_green, floor) - elapsed))
