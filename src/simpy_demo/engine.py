"""SimPy simulation engine for production line digital twin."""

import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import simpy

from simpy_demo.equipment import Equipment
from simpy_demo.loader import ConfigLoader, ResolvedConfig, RunConfig
from simpy_demo.models import MachineConfig, MaterialType, Product, ProductConfig


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
                env,
                machines,
                buffers,
                telemetry_data,
                run.telemetry_interval_sec,
                start_time,
                resolved.product,
            )
        )

        # 7. Run simulation
        duration_sec = run.duration_hours * 3600
        print(f"Starting Simulation: {run.name} ({run.duration_hours} hrs)...")
        env.run(until=duration_sec)

        # 8. Compile results
        return self._compile_results(machines, telemetry_data, start_time)

    def run_config(
        self,
        run: RunConfig,
        machine_configs: List[MachineConfig],
        product: Optional[ProductConfig] = None,
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
                env,
                machines,
                buffers,
                telemetry_data,
                run.telemetry_interval_sec,
                start_time,
                product,
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
        product: Optional[ProductConfig] = None,
    ):
        """Capture telemetry at regular intervals (incremental values per interval)."""
        # Track previous values for delta calculation
        prev = {
            "tubes": 0,
            "cases": 0,
            "pallets": 0,
            "good": 0,
            "defective": 0,
            "defects_created": 0,
            "defects_detected": 0,
            "material_cost": 0.0,
            "conversion_cost": 0.0,
            "revenue": 0.0,
        }

        while True:
            snapshot = {
                "time": env.now,
                "datetime": start_time + timedelta(seconds=env.now) if start_time else None,
            }

            # SKU Context (if product defined)
            if product:
                snapshot["sku_name"] = product.name
                snapshot["sku_description"] = product.description
                snapshot["size_oz"] = product.size_oz
                snapshot["units_per_case"] = product.units_per_case
                snapshot["cases_per_pallet"] = product.cases_per_pallet

            # Production Counts (aggregate across machines by type)
            total_tubes = sum(m.tubes_produced for m in machines)
            total_cases = sum(m.cases_produced for m in machines)
            total_pallets = sum(m.pallets_produced for m in machines)
            total_defects_created = sum(m.defects_created for m in machines)
            total_defects_detected = sum(m.defects_detected for m in machines)

            # Find palletizer to determine good vs defective pallets
            palletizer = next(
                (m for m in machines if m.cfg.output_type == MaterialType.PALLET), None
            )
            total_defective = palletizer.defects_escaped if palletizer else 0
            total_good = total_pallets - total_defective

            # Store incremental values (delta from previous interval)
            snapshot["tubes_produced"] = total_tubes - prev["tubes"]
            snapshot["cases_produced"] = total_cases - prev["cases"]
            snapshot["pallets_produced"] = total_pallets - prev["pallets"]
            snapshot["good_pallets"] = total_good - prev["good"]
            snapshot["defective_pallets"] = total_defective - prev["defective"]
            snapshot["defects_created"] = total_defects_created - prev["defects_created"]
            snapshot["defects_detected"] = total_defects_detected - prev["defects_detected"]

            # Update previous values
            prev["tubes"] = total_tubes
            prev["cases"] = total_cases
            prev["pallets"] = total_pallets
            prev["good"] = total_good
            prev["defective"] = total_defective
            prev["defects_created"] = total_defects_created
            prev["defects_detected"] = total_defects_detected

            # Economic Data (if product defined)
            if product:
                # Material cost: all pallets consume materials (includes scrap)
                material_cost = total_pallets * product.material_cost

                # Conversion cost: sum across all machines
                conversion_cost = sum(m.conversion_cost for m in machines)

                # Revenue: only good pallets sell
                revenue = total_good * product.selling_price

                # Store incremental economic values
                snapshot["material_cost"] = round(material_cost - prev["material_cost"], 2)
                snapshot["conversion_cost"] = round(conversion_cost - prev["conversion_cost"], 2)
                snapshot["revenue"] = round(revenue - prev["revenue"], 2)
                snapshot["gross_margin"] = round(
                    snapshot["revenue"] - snapshot["material_cost"] - snapshot["conversion_cost"], 2
                )

                # Update previous economic values
                prev["material_cost"] = material_cost
                prev["conversion_cost"] = conversion_cost
                prev["revenue"] = revenue

            # Log Buffer Levels (these stay as current values, not deltas)
            for name, buf in buffers.items():
                if buf.capacity != float("inf"):
                    snapshot[f"{name}_level"] = len(buf.items)
                    snapshot[f"{name}_cap"] = buf.capacity

            # Log Machine States (current state, not delta)
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
