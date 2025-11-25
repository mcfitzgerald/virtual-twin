import simpy
import random
from typing import List, Optional

from simpy_demo.models import MachineConfig, Product, MaterialType


class SmartEquipment:
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

        # Centralized Logs
        self.event_log = []

        self.process = env.process(self.run())

    def log(self, new_state):
        """Records state transitions for OEE calculation."""
        if self.state != new_state:
            self.event_log.append(
                {
                    "timestamp": self.env.now,
                    "machine": self.cfg.name,
                    "state": self.state,
                    "event_type": "end",
                }
            )
            self.state = new_state
            self.event_log.append(
                {
                    "timestamp": self.env.now,
                    "machine": self.cfg.name,
                    "state": self.state,
                    "event_type": "start",
                }
            )

    def run(self):
        self.log("STARVED")

        while True:
            # --- PHASE 1: COLLECT (Starvation Logic) ---
            # Represents "Idling" - Waiting for material
            inputs = []
            for _ in range(self.cfg.batch_in):
                item = yield self.upstream.get()
                inputs.append(item)

            # --- PHASE 2: BREAKDOWN CHECK (Availability Loss) ---
            # Major failures based on elapsed time (MTBF)
            if self.cfg.mtbf_min:
                # Poisson probability of failure during this cycle
                p_fail = 1.0 - 2.718 ** -(
                    self.cfg.cycle_time_sec / (self.cfg.mtbf_min * 60)
                )
                if random.random() < p_fail:
                    self.log("DOWN")
                    # Stochastic repair time
                    repair_time = random.expovariate(1.0 / (self.cfg.mttr_min * 60))
                    yield self.env.timeout(repair_time)

            # --- PHASE 3: MICROSTOP CHECK (Performance Loss) ---
            # Minor jams based on cycle count (Jam Rate)
            if self.cfg.jam_prob > 0 and random.random() < self.cfg.jam_prob:
                self.log("JAMMED")
                # Fixed or small variable time to clear jam
                yield self.env.timeout(self.cfg.jam_time_sec)

            # --- PHASE 4: EXECUTE (Value Add) ---
            self.log("EXECUTE")
            yield self.env.timeout(self.cfg.cycle_time_sec)

            # --- PHASE 5: TRANSFORM (Traceability Logic) ---
            output_item = self._transform_material(inputs)
            self.items_produced += 1

            # --- PHASE 6: INSPECT & ROUTE (Quality Logic) ---
            routed_to_reject = False
            if self.cfg.detection_prob > 0 and output_item.is_defective:
                if random.random() < self.cfg.detection_prob:
                    routed_to_reject = True

            # If downstream is full, we enter BLOCKED state (Constraint)
            self.log("BLOCKED")
            if routed_to_reject and self.reject_store:
                yield self.reject_store.put(output_item)
            else:
                yield self.downstream.put(output_item)

            # If we succeed, we go back to waiting (Starved)
            self.log("STARVED")

    def _transform_material(self, inputs: List[Product]) -> Product:
        # 1. Inherit Defects
        has_inherited_defect = any(i.is_defective for i in inputs)

        # 2. Create New Defect?
        new_defect = random.random() < self.cfg.defect_rate
        is_bad = has_inherited_defect or new_defect

        # 3. Create Payload
        genealogy = [i.uid for i in inputs]

        # 4. Factory Construction
        if self.cfg.output_type == MaterialType.TUBE:
            return Product(
                type=MaterialType.TUBE,
                created_at=self.env.now,
                parent_machine=self.cfg.name,
                is_defective=is_bad,
                genealogy=genealogy,
                telemetry={"fill_level": random.gauss(100, 1.0)},
            )
        elif self.cfg.output_type == MaterialType.CASE:
            return Product(
                type=MaterialType.CASE,
                created_at=self.env.now,
                parent_machine=self.cfg.name,
                is_defective=is_bad,
                genealogy=genealogy,
                telemetry={"weight": sum([100 for _ in inputs]) + 50},
            )
        elif self.cfg.output_type == MaterialType.PALLET:
            return Product(
                type=MaterialType.PALLET,
                created_at=self.env.now,
                parent_machine=self.cfg.name,
                is_defective=is_bad,
                genealogy=genealogy,
                telemetry={"location": "Warehouse_A"},
            )

        # Pass-through (e.g. Inspection Station)
        return inputs[0]
