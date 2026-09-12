# Model assumptions and limits

## What the simulator actually does

SUMO implements longitudinal/lateral motion, junction right-of-way and pedestrian
walking. Simroad generates inputs, applies policies through TraCI, and measures
outputs. Vehicle speed/acceleration units are m/s and m/s²; lengths are meters;
headways and simulation times are seconds. Fleet shares sum to one.

The step-length <= active minimum tau check guards an important SUMO safety
condition. It does **not** guarantee collision-free behavior in every circumstance:
deliberate junction violations, unsafe configured parameters, pedestrian interactions
and geometry still matter. Collision reports count physical collisions
(`collision.mingap-factor=0`), not every desired-gap violation. Consecutive reports
for the same unordered pair and event type are counted as one episode. A new
episode starts after at least one step without that collision.

## Demand

Each zone's total daily trips equal population times its mode-specific trip rate.
Gaussian pulses integrate to one day and split trips by pulse weight and direction.
Each bin draws a Poisson trip count; departures are uniform inside the bin. Five
minutes is the default bin width. This approximates the curve within a bin while
preserving its expected integrated volume. School peaks represent arrival before
start and departure after dismissal; all timings are editable.

Destinations/origins are sampled from zone edges and the rest of the network,
conditional on class-specific connectivity. This is a transparent baseline, not a
surveyed OD matrix, gravity model, shortest-route equilibrium or trip-chain model.
If 40 attempts cannot find a connected OD pair, generation fails and writes its
diagnostic counts; it does not quietly discard travelers. Gateway flows let users
supply known edge-to-edge vehicle demand. Calibration is specific to this demand
construction and window. Default pulses/populations are illustrative priors;
no invented literature citations are attached to their numeric values.

## Zone interventions

Speed caps and encroachment affect whole intersecting road edges. Circle matching
uses segment distance; polygon matching samples road centerlines every 5 m, so
very thin polygons should use explicit edge IDs. A zone touching only a tiny
part of a long edge still changes the entire edge: split it in Netedit for precision.
Overlapping zones apply the lowest speed and largest encroachment once.
Width reduction is a sublane capacity approximation; vendors are not individual
objects. An office's parking probability creates an in-lane destination stop
(double-parking obstruction), not a search loop or a parking-space allocation model.

Hospital pedestrian minimum walk time is protected conservatively: the highest
configured zone minimum and slowest configured walking speed are used globally
for signalized crossing service, including crossing-length clearance. This can
overestimate required service outside the hospital; explicit spatial refinement
is a future improvement. Emergency dispatch and preemption are not implemented.

## Crossings and transit

Signalized crossings obey the junction's program. Zebra crossings use SUMO's
priority semantics. Informal crossings can be specified at existing unregulated
junctions with pedestrian priority disabled. Roads must already be split at
desired midblock sites; spontaneous off-network jaywalking is not simulated.

The pressure strategy shortens/extends green service based on queues and waiting
persons, cycles through the existing safe phase order, and leaves clearance
phases intact. It does not suppress every empty pedestrian phase; a fully
button-only pedestrian controller is a future extension. Minimum service can
exceed max_green when required for pedestrian clearance.

Transit routes use explicit connected edge sequences and bus-stop lane positions.
Dwell time is a normal draw clipped at zero. `blocks_lane: true` creates a normal
in-lane stop; `false` uses SUMO off-road parking during dwell as a simplified bay.
It does not model bay entry/exit geometry. Use a supplied SUMO network with real
bay lanes for geometry-sensitive studies. Fleet buses not assigned to a scheduled
service behave as ordinary through vehicles.

## Measurement and inference

Throughput counts vehicles finishing within the window. Completed-trip mean time
loss can have survivor bias; reports also expose unfinished and not-inserted
vehicles, and time-integrated stopped vehicle counts. Start/end transients are
part of the configured window; no hidden warm-up is discarded. Teleport recovery
is disabled so gridlock stays visible. SUMO collision and trip XML files accompany
reports for inspection.

Paired demand is identical across strategies; trajectories and SUMO random-number
consumption may diverge after a policy intervenes. Student t intervals assume
independent seeds and approximately normal mean differences. Use enough seeds,
inspect outliers, and preselect a primary endpoint. Multiple endpoints are
exploratory and receive no multiple-comparison correction.

GEH validation uses independent seeds, not independent field sites or dates.
Grid fitting demand/headway/mix can be nonidentifiable from counts alone. A passed
count fit is insufficient evidence of realistic driving behavior. The artifact
records the user-declared observation provenance; the software cannot verify
whether a survey actually occurred. It is an auditable local artifact, not a
tamper-proof certification system.

## Primary references

- [SUMO sublane model](https://sumo.dlr.de/docs/Simulation/SublaneModel.html)
- [SUMO safety and reaction time](https://sumo.dlr.de/docs/Simulation/Safety.html)
- [SUMO pedestrian modeling](https://sumo.dlr.de/docs/Simulation/Pedestrians.html)
- [SUMO plain XML and crossings](https://sumo.dlr.de/docs/Networks/PlainXML.html)
- [SUMO traffic light programs](https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html)
- [SUMO TraCI collision retrieval](https://sumo.dlr.de/docs/TraCI/Simulation_Value_Retrieval.html)
- [SUMO OSM import](https://sumo.dlr.de/docs/Networks/Import/OpenStreetMap.html)

The GEH acceptance thresholds are the project specification's criteria. Site
acceptance standards may require additional measures and independent validation.
