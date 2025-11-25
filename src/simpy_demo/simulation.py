import simpy
import random
import pandas as pd
from typing import List, Dict

from simpy_demo.models import ScenarioConfig, Product, MaterialType
from simpy_demo.equipment import SmartEquipment


class ProductionLine:
    def __init__(self, config: ScenarioConfig):
        self.cfg = config
        self.env = simpy.Environment()
        self.machines: List[SmartEquipment] = []
        self.buffers: Dict[str, simpy.Store] = {}

        if self.cfg.random_seed:
            random.seed(self.cfg.random_seed)

        self._build_layout()

        # Start Data Collector
        self.env.process(self._monitor_process(interval=1.0))
        self.telemetry_data = []

    def _build_layout(self):
        # 1. Infinite Source
        source = simpy.Store(self.env, capacity=float("inf"))
        # Pre-fill with generic raw material
        for i in range(100000):
            source.put(
                Product(
                    type=MaterialType.NONE,
                    created_at=0,
                    parent_machine="Raw",
                    genealogy=[],
                )
            )

        # 2. Reject Bin (Infinite Sink)
        self.reject_bin = simpy.Store(self.env, capacity=float("inf"))

        # 3. Build Line
        current_upstream = source

        for i, m_conf in enumerate(self.cfg.layout):
            # Create Buffer (Constraint)
            buffer_name = f"Buf_{m_conf.name}"
            # Last machine output goes to infinite Sink
            cap = (
                float("inf")
                if i == len(self.cfg.layout) - 1
                else m_conf.buffer_capacity
            )

            downstream = simpy.Store(self.env, capacity=cap)
            self.buffers[buffer_name] = downstream  # Track for monitoring

            # Create Machine
            machine = SmartEquipment(
                self.env,
                m_conf,
                upstream=current_upstream,
                downstream=downstream,
                reject_store=self.reject_bin if m_conf.detection_prob > 0 else None,
            )
            self.machines.append(machine)
            current_upstream = downstream

    def _monitor_process(self, interval: float):
        """Periodically records buffer levels and machine states."""
        while True:
            snapshot = {"time": self.env.now}

            # Log Buffer Levels (Constraint Analysis)
            for name, buf in self.buffers.items():
                if buf.capacity != float("inf"):
                    snapshot[f"{name}_level"] = len(buf.items)
                    snapshot[f"{name}_cap"] = buf.capacity

            # Log Machine States (Status Analysis)
            for m in self.machines:
                snapshot[f"{m.cfg.name}_state"] = m.state
                snapshot[f"{m.cfg.name}_output"] = m.items_produced

            self.telemetry_data.append(snapshot)
            yield self.env.timeout(interval)

    def run(self):
        print(f"Starting Simulation: {self.cfg.name} ({self.cfg.duration_hours} hrs)...")
        self.env.run(until=self.cfg.duration_hours * 3600)
        return self._compile_results()

    def _compile_results(self):
        # 1. Telemetry (Time-Series)
        df_telemetry = pd.DataFrame(self.telemetry_data)

        # 2. Events (State Log)
        events = []
        for m in self.machines:
            events.extend(m.event_log)
        df_events = pd.DataFrame(events)

        return df_telemetry, df_events
