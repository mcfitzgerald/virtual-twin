"""SimPy simulation engine for production line digital twin."""

import random
from typing import Dict, List, Tuple, Type

import pandas as pd
import simpy

from simpy_demo.config import EquipmentParams, ScenarioConfig
from simpy_demo.equipment import Equipment
from simpy_demo.models import (
    MachineConfig,
    MaterialType,
    PerformanceParams,
    Product,
    QualityParams,
    ReliabilityParams,
)
from simpy_demo.topology import CosmeticsLine, Station


class SimulationEngine:
    """Simulation engine that combines topology + baseline + scenario."""

    def __init__(
        self,
        topology: type[CosmeticsLine],
        baseline: Dict[str, EquipmentParams],
    ):
        self.topology = topology
        self.baseline = baseline

    def run(self, scenario: ScenarioConfig) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Run scenario and return (telemetry_df, events_df)."""
        # 1. Set random seed
        if scenario.random_seed is not None:
            random.seed(scenario.random_seed)

        # 2. Create SimPy environment
        env = simpy.Environment()

        # 3. Build machine configs by merging baseline + scenario overrides
        machine_configs = self._build_configs(scenario)

        # 4. Build production line
        machines, buffers, reject_bin = self._build_layout(env, machine_configs)

        # 5. Start monitoring
        telemetry_data: List[dict] = []
        env.process(self._monitor_process(env, machines, buffers, telemetry_data))

        # 6. Run simulation
        duration_sec = scenario.duration_hours * 3600
        print(f"Starting Simulation: {scenario.name} ({scenario.duration_hours} hrs)...")
        env.run(until=duration_sec)

        # 7. Compile results
        return self._compile_results(machines, telemetry_data)

    def _build_configs(self, scenario: ScenarioConfig) -> List[MachineConfig]:
        """Merge topology + baseline + scenario into MachineConfigs."""
        configs = []
        for station in self.topology.stations:
            # Start with baseline (or empty if not defined)
            base = self.baseline.get(station.name, EquipmentParams())
            override = scenario.equipment.get(station.name, EquipmentParams())

            # Merge: override wins over baseline
            config = MachineConfig(
                name=station.name,
                uph=override.uph or base.uph or 10000,
                batch_in=station.batch_in,
                output_type=station.output_type,
                buffer_capacity=override.buffer_capacity or base.buffer_capacity or 50,
                reliability=self._merge_params(
                    base.reliability, override.reliability, ReliabilityParams
                ),
                performance=self._merge_params(
                    base.performance, override.performance, PerformanceParams
                ),
                quality=self._merge_params(
                    base.quality, override.quality, QualityParams
                ),
            )
            configs.append(config)
        return configs

    def _merge_params(
        self,
        base: ReliabilityParams | PerformanceParams | QualityParams | None,
        override: ReliabilityParams | PerformanceParams | QualityParams | None,
        param_class: Type[ReliabilityParams]
        | Type[PerformanceParams]
        | Type[QualityParams],
    ) -> ReliabilityParams | PerformanceParams | QualityParams:
        """Merge two param objects, override wins for non-None fields."""
        if base is None and override is None:
            return param_class()
        if base is None:
            return override  # type: ignore
        if override is None:
            return base
        # Field-level merge
        merged = {}
        for field in param_class.model_fields:
            override_val = getattr(override, field, None)
            base_val = getattr(base, field, None)
            merged[field] = override_val if override_val is not None else base_val
        return param_class(**merged)

    def _build_layout(
        self, env: simpy.Environment, configs: List[MachineConfig]
    ) -> Tuple[List[Equipment], Dict[str, simpy.Store], simpy.Store]:
        """Build SimPy stores and Equipment instances."""
        machines: List[Equipment] = []
        buffers: Dict[str, simpy.Store] = {}

        # 1. Infinite Source
        source = simpy.Store(env, capacity=float("inf"))
        # Pre-fill with generic raw material
        for _ in range(100000):
            source.put(
                Product(
                    type=MaterialType.NONE,
                    created_at=0,
                    parent_machine="Raw",
                    genealogy=[],
                )
            )

        # 2. Reject Bin (Infinite Sink)
        reject_bin = simpy.Store(env, capacity=float("inf"))

        # 3. Build Line
        current_upstream = source

        for i, m_conf in enumerate(configs):
            # Create Buffer
            buffer_name = f"Buf_{m_conf.name}"
            # Last machine output goes to infinite Sink
            cap = float("inf") if i == len(configs) - 1 else m_conf.buffer_capacity

            downstream = simpy.Store(env, capacity=cap)
            buffers[buffer_name] = downstream

            # Create Machine
            machine = Equipment(
                env,
                m_conf,
                upstream=current_upstream,
                downstream=downstream,
                reject_store=reject_bin if m_conf.quality.detection_prob > 0 else None,
            )
            machines.append(machine)
            current_upstream = downstream

        return machines, buffers, reject_bin

    def _monitor_process(
        self,
        env: simpy.Environment,
        machines: List[Equipment],
        buffers: Dict[str, simpy.Store],
        telemetry_data: List[dict],
        interval: float = 1.0,
    ):
        """Capture telemetry at regular intervals."""
        while True:
            snapshot = {"time": env.now}

            # Log Buffer Levels
            for name, buf in buffers.items():
                if buf.capacity != float("inf"):
                    snapshot[f"{name}_level"] = len(buf.items)
                    snapshot[f"{name}_cap"] = buf.capacity

            # Log Machine States
            for m in machines:
                snapshot[f"{m.cfg.name}_state"] = m.state
                snapshot[f"{m.cfg.name}_output"] = m.items_produced

            telemetry_data.append(snapshot)
            yield env.timeout(interval)

    def _compile_results(
        self, machines: List[Equipment], telemetry_data: List[dict]
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Compile DataFrames from simulation data."""
        # 1. Telemetry (Time-Series)
        df_telemetry = pd.DataFrame(telemetry_data)

        # 2. Events (State Log)
        events = []
        for m in machines:
            events.extend(m.event_log)
        df_events = pd.DataFrame(events)

        return df_telemetry, df_events
