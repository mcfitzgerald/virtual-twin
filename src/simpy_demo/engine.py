"""SimPy simulation engine for production line digital twin."""

import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import simpy

from simpy_demo.equipment import Equipment
from simpy_demo.loader import ConfigLoader, ResolvedConfig, RunConfig
from simpy_demo.models import MachineConfig, MaterialType, Product


class SimulationEngine:
    """Simulation engine that runs from resolved YAML configuration."""

    def __init__(self, config_dir: str = "config"):
        self.loader = ConfigLoader(config_dir)

    def run(self, run_name: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Run simulation by run config name and return (telemetry_df, events_df)."""
        resolved = self.loader.resolve_run(run_name)
        return self.run_resolved(resolved)

    def run_resolved(
        self, resolved: ResolvedConfig
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Run simulation from a fully resolved configuration."""
        run = resolved.run

        # 1. Set random seed
        if run.random_seed is not None:
            random.seed(run.random_seed)

        # 2. Determine start time (config or now)
        start_time = run.start_time or datetime.now()

        # 3. Create SimPy environment
        env = simpy.Environment()

        # 4. Build machine configs from resolved config
        machine_configs = self.loader.build_machine_configs(resolved)

        # 5. Build production line
        machines, buffers, reject_bin = self._build_layout(env, machine_configs)

        # 6. Start monitoring
        telemetry_data: List[dict] = []
        env.process(
            self._monitor_process(
                env, machines, buffers, telemetry_data, run.telemetry_interval_sec, start_time
            )
        )

        # 7. Run simulation
        duration_sec = run.duration_hours * 3600
        print(f"Starting Simulation: {run.name} ({run.duration_hours} hrs)...")
        env.run(until=duration_sec)

        # 8. Compile results
        return self._compile_results(machines, telemetry_data, start_time)

    def run_config(
        self, run: RunConfig, machine_configs: List[MachineConfig]
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Run simulation from RunConfig and pre-built MachineConfigs (programmatic use)."""
        # 1. Set random seed
        if run.random_seed is not None:
            random.seed(run.random_seed)

        # 2. Determine start time (config or now)
        start_time = run.start_time or datetime.now()

        # 3. Create SimPy environment
        env = simpy.Environment()

        # 4. Build production line
        machines, buffers, reject_bin = self._build_layout(env, machine_configs)

        # 5. Start monitoring
        telemetry_data: List[dict] = []
        env.process(
            self._monitor_process(
                env, machines, buffers, telemetry_data, run.telemetry_interval_sec, start_time
            )
        )

        # 6. Run simulation
        duration_sec = run.duration_hours * 3600
        print(f"Starting Simulation: {run.name} ({run.duration_hours} hrs)...")
        env.run(until=duration_sec)

        # 7. Compile results
        return self._compile_results(machines, telemetry_data, start_time)

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
        start_time: Optional[datetime] = None,
    ):
        """Capture telemetry at regular intervals."""
        while True:
            snapshot = {
                "time": env.now,
                "datetime": start_time + timedelta(seconds=env.now) if start_time else None,
            }

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
        self,
        machines: List[Equipment],
        telemetry_data: List[dict],
        start_time: Optional[datetime] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Compile DataFrames from simulation data."""
        # 1. Telemetry (Time-Series) - datetime already embedded
        df_telemetry = pd.DataFrame(telemetry_data)

        # Reorder columns to put datetime first if present
        if "datetime" in df_telemetry.columns:
            cols = ["datetime", "time"] + [
                c for c in df_telemetry.columns if c not in ["datetime", "time"]
            ]
            df_telemetry = df_telemetry[cols]

        # 2. Events (State Log)
        events = []
        for m in machines:
            events.extend(m.event_log)
        df_events = pd.DataFrame(events)

        # Add datetime to events
        if start_time and not df_events.empty:
            df_events["datetime"] = df_events["timestamp"].apply(
                lambda s: start_time + timedelta(seconds=s)
            )
            # Reorder columns
            cols = ["datetime", "timestamp"] + [
                c for c in df_events.columns if c not in ["datetime", "timestamp"]
            ]
            df_events = df_events[cols]

        return df_telemetry, df_events
