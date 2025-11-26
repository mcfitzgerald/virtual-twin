"""Equipment simulation class with 6-phase cycle."""

import math
import random
from typing import TYPE_CHECKING, List, Optional

import simpy

from simpy_demo.models import MachineConfig, MaterialType, Product

if TYPE_CHECKING:
    from simpy_demo.factories.telemetry import TelemetryGenerator
    from simpy_demo.simulation.layout import NodeConnections


class Equipment:
    """Generic machine simulator with configurable behavior.

    Follows a 6-phase cycle where config params determine which behaviors activate:
    1. COLLECT: Wait for upstream material (starvation)
    2. BREAKDOWN: Poisson probability check (if reliability.mtbf_min is set)
    3. MICROSTOP: Bernoulli per-cycle check (if performance.jam_prob > 0)
    4. EXECUTE: Process for cycle_time_sec
    5. TRANSFORM: Create output based on output_type
    6. INSPECT/ROUTE: Route defectives (if quality.detection_prob > 0)

    Supports both linear (single upstream/downstream) and graph-based
    (multiple upstream/downstream with conditional routing) topologies.
    """

    def __init__(
        self,
        env: simpy.Environment,
        config: MachineConfig,
        upstream: simpy.Store,
        downstream: simpy.Store,
        reject_store: Optional[simpy.Store],
        telemetry_gen: Optional["TelemetryGenerator"] = None,
        connections: Optional["NodeConnections"] = None,
    ):
        """Initialize equipment.

        Args:
            env: SimPy environment
            config: Machine configuration
            upstream: Primary upstream store (for backward compatibility)
            downstream: Primary downstream store (for backward compatibility)
            reject_store: Store for rejected products
            telemetry_gen: Telemetry generator
            connections: Optional graph-based connections for multi-path routing
        """
        self.env = env
        self.cfg = config
        self.upstream = upstream
        self.downstream = downstream
        self.reject_store = reject_store
        self.telemetry_gen = telemetry_gen

        # Graph-based connections (optional)
        self._connections = connections
        self._use_graph_routing = connections is not None and len(
            connections.downstream_routes
        ) > 1

        self.items_produced = 0
        self.state = "IDLE"
        self.state_start_time = 0.0  # Track time in current state

        # Production counters by material type
        self.tubes_produced = 0
        self.cases_produced = 0
        self.pallets_produced = 0

        # Quality counters
        self.defects_created = 0
        self.defects_detected = 0
        self.defects_escaped = 0

        # Time tracking by state (for conversion cost)
        self.time_in_state: dict[str, float] = {
            "STARVED": 0.0,
            "EXECUTE": 0.0,
            "DOWN": 0.0,
            "JAMMED": 0.0,
            "BLOCKED": 0.0,
        }

        # Centralized Logs
        self.event_log: List[dict] = []

        self.process = env.process(self.run())

    def log(self, new_state: str) -> None:
        """Records state transitions for OEE calculation and time tracking."""
        if self.state != new_state:
            # Track time spent in previous state
            time_spent = self.env.now - self.state_start_time
            if self.state in self.time_in_state:
                self.time_in_state[self.state] += time_spent

            self.event_log.append(
                {
                    "timestamp": self.env.now,
                    "machine": self.cfg.name,
                    "state": self.state,
                    "event_type": "end",
                }
            )
            self.state = new_state
            self.state_start_time = self.env.now
            self.event_log.append(
                {
                    "timestamp": self.env.now,
                    "machine": self.cfg.name,
                    "state": self.state,
                    "event_type": "start",
                }
            )

    def run(self):
        """Main process loop implementing 6-phase cycle."""
        self.log("STARVED")

        while True:
            # --- PHASE 1: COLLECT (Starvation Logic) ---
            inputs = []
            for _ in range(self.cfg.batch_in):
                item = yield self.upstream.get()
                inputs.append(item)

            # --- PHASE 2: BREAKDOWN CHECK (Availability Loss) ---
            if self.cfg.reliability.mtbf_min:
                # Poisson probability: P(fail) = 1 - e^(-cycle_time/mtbf)
                mtbf_sec = self.cfg.reliability.mtbf_min * 60  # minutes to seconds
                p_fail = 1.0 - math.exp(-self.cfg.cycle_time_sec / mtbf_sec)
                if random.random() < p_fail:
                    self.log("DOWN")
                    repair_time = random.expovariate(
                        1.0 / (self.cfg.reliability.mttr_min * 60)
                    )
                    yield self.env.timeout(repair_time)

            # --- PHASE 3: MICROSTOP CHECK (Performance Loss) ---
            if (
                self.cfg.performance.jam_prob > 0
                and random.random() < self.cfg.performance.jam_prob
            ):
                self.log("JAMMED")
                yield self.env.timeout(self.cfg.performance.jam_time_sec)

            # --- PHASE 4: EXECUTE (Value Add) ---
            self.log("EXECUTE")
            yield self.env.timeout(self.cfg.cycle_time_sec)

            # --- PHASE 5: TRANSFORM (Traceability Logic) ---
            output_item, new_defect = self._transform_material(inputs)
            self.items_produced += 1

            # Track production by type
            if output_item.type == MaterialType.TUBE:
                self.tubes_produced += 1
            elif output_item.type == MaterialType.CASE:
                self.cases_produced += 1
            elif output_item.type == MaterialType.PALLET:
                self.pallets_produced += 1

            # Track defects
            if new_defect:
                self.defects_created += 1

            # --- PHASE 6: INSPECT & ROUTE (Quality Logic) ---
            routed_to_reject = False
            if self.cfg.quality.detection_prob > 0 and output_item.is_defective:
                if random.random() < self.cfg.quality.detection_prob:
                    routed_to_reject = True
                    self.defects_detected += 1
                else:
                    self.defects_escaped += 1

            # If downstream is full, we enter BLOCKED state
            self.log("BLOCKED")

            # Route output using graph-based routing or legacy routing
            if self._use_graph_routing and self._connections:
                # Graph-based routing: use connections to determine destination
                destination = self._connections.get_route(output_item)
                yield destination.put(output_item)
            elif routed_to_reject and self.reject_store:
                # Legacy routing: route defectives to reject store
                yield self.reject_store.put(output_item)
            else:
                # Legacy routing: route to primary downstream
                yield self.downstream.put(output_item)

            # Back to waiting for material
            self.log("STARVED")

    def _transform_material(self, inputs: List[Product]) -> tuple[Product, bool]:
        """Transform inputs into output product based on config.

        Uses TelemetryGenerator if available, otherwise falls back to pass-through.

        Returns:
            Tuple of (output_product, new_defect_created)
        """
        # 1. Inherit Defects
        has_inherited_defect = any(i.is_defective for i in inputs)

        # 2. Create New Defect?
        new_defect = random.random() < self.cfg.quality.defect_rate
        is_bad = has_inherited_defect or new_defect

        # 3. Create Genealogy
        genealogy = [i.uid for i in inputs]

        # 4. Pass-through for NONE output type (e.g., Inspection Station)
        if self.cfg.output_type == MaterialType.NONE:
            return (inputs[0], False)

        # 5. Generate telemetry from config if available
        material_type_str = self.cfg.output_type.name  # "TUBE", "CASE", "PALLET"
        telemetry: dict = {}

        if self.telemetry_gen and self.telemetry_gen.has_config_for(material_type_str):
            telemetry = self.telemetry_gen.generate(material_type_str, inputs)

        # 6. Create output product
        return (
            Product(
                type=self.cfg.output_type,
                created_at=self.env.now,
                parent_machine=self.cfg.name,
                is_defective=is_bad,
                genealogy=genealogy,
                telemetry=telemetry,
            ),
            new_defect,
        )

    @property
    def total_time_sec(self) -> float:
        """Total wall-clock time spent by this machine (for conversion cost)."""
        return sum(self.time_in_state.values())

    @property
    def conversion_cost(self) -> float:
        """Calculate conversion cost based on total time and cost rates."""
        hours = self.total_time_sec / 3600.0
        return hours * self.cfg.cost_rates.total_per_hour
