"""Equipment simulation class with 6-phase cycle."""

import random
from typing import List, Optional

import simpy

from simpy_demo.models import MachineConfig, MaterialType, Product


class Equipment:
    """Generic machine simulator with configurable behavior.

    Follows a 6-phase cycle where config params determine which behaviors activate:
    1. COLLECT: Wait for upstream material (starvation)
    2. BREAKDOWN: Poisson probability check (if reliability.mtbf_min is set)
    3. MICROSTOP: Bernoulli per-cycle check (if performance.jam_prob > 0)
    4. EXECUTE: Process for cycle_time_sec
    5. TRANSFORM: Create output based on output_type
    6. INSPECT/ROUTE: Route defectives (if quality.detection_prob > 0)
    """

    def __init__(
        self,
        env: simpy.Environment,
        config: MachineConfig,
        upstream: simpy.Store,
        downstream: simpy.Store,
        reject_store: Optional[simpy.Store],
    ):
        self.env = env
        self.cfg = config
        self.upstream = upstream
        self.downstream = downstream
        self.reject_store = reject_store

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
                p_fail = 1.0 - 2.718 ** -(
                    self.cfg.cycle_time_sec / (self.cfg.reliability.mtbf_min * 60)
                )
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
            if routed_to_reject and self.reject_store:
                yield self.reject_store.put(output_item)
            else:
                yield self.downstream.put(output_item)

            # Back to waiting for material
            self.log("STARVED")

    def _transform_material(self, inputs: List[Product]) -> tuple[Product, bool]:
        """Transform inputs into output product based on config.

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

        # 4. Factory Construction based on output_type
        if self.cfg.output_type == MaterialType.TUBE:
            return (
                Product(
                    type=MaterialType.TUBE,
                    created_at=self.env.now,
                    parent_machine=self.cfg.name,
                    is_defective=is_bad,
                    genealogy=genealogy,
                    telemetry={"fill_level": random.gauss(100, 1.0)},
                ),
                new_defect,
            )
        elif self.cfg.output_type == MaterialType.CASE:
            return (
                Product(
                    type=MaterialType.CASE,
                    created_at=self.env.now,
                    parent_machine=self.cfg.name,
                    is_defective=is_bad,
                    genealogy=genealogy,
                    telemetry={"weight": sum([100 for _ in inputs]) + 50},
                ),
                new_defect,
            )
        elif self.cfg.output_type == MaterialType.PALLET:
            return (
                Product(
                    type=MaterialType.PALLET,
                    created_at=self.env.now,
                    parent_machine=self.cfg.name,
                    is_defective=is_bad,
                    genealogy=genealogy,
                    telemetry={"location": "Warehouse_A"},
                ),
                new_defect,
            )

        # Pass-through (e.g. Inspection Station)
        return (inputs[0], False)

    @property
    def total_time_sec(self) -> float:
        """Total wall-clock time spent by this machine (for conversion cost)."""
        return sum(self.time_in_state.values())

    @property
    def conversion_cost(self) -> float:
        """Calculate conversion cost based on total time and cost rates."""
        hours = self.total_time_sec / 3600.0
        return hours * self.cfg.cost_rates.total_per_hour
