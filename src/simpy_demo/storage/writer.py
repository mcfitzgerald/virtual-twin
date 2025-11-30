"""DuckDB writer for persisting simulation results."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

import duckdb
import pandas as pd

from simpy_demo.storage.schema import create_tables

if TYPE_CHECKING:
    from simpy_demo.loader import ResolvedConfig

__version__ = "0.14.0"


class DuckDBWriter:
    """Writes simulation results to DuckDB database."""

    def __init__(self, db_path: Path):
        """Initialize writer and ensure schema exists.

        Args:
            db_path: Path to DuckDB database file
        """
        self.db_path = db_path
        self.conn = duckdb.connect(str(db_path))
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create tables if they don't exist."""
        create_tables(self.conn)

    def store_run(
        self,
        resolved: "ResolvedConfig",
        df_ts: pd.DataFrame,
        df_ev: pd.DataFrame,
        *,
        debug_events: bool = False,
        df_state_summary: Optional[pd.DataFrame] = None,
        df_events_detail: Optional[pd.DataFrame] = None,
    ) -> int:
        """Store complete simulation results.

        Args:
            resolved: Resolved configuration used for the simulation
            df_ts: Telemetry DataFrame (time-series)
            df_ev: Events DataFrame (state transitions)
            debug_events: If True, store full events table (default: False)
            df_state_summary: Pre-aggregated state summary from EventAggregator
            df_events_detail: Filtered event details from EventAggregator

        Returns:
            run_id of the stored simulation
        """
        # 1. Insert simulation_runs record
        run_id = self._insert_simulation_run(resolved)

        # 2. Insert telemetry (bulk)
        self._insert_telemetry(run_id, df_ts)

        # 3. Insert machine_telemetry (extracted from df_ts)
        self._insert_machine_telemetry(run_id, df_ts)

        # 4. Insert state_summary (always, if provided)
        if df_state_summary is not None:
            self._insert_state_summary(run_id, df_state_summary)

        # 5. Insert events_detail (always, if provided)
        if df_events_detail is not None:
            self._insert_events_detail(run_id, df_events_detail)

        # 6. Insert full events (ONLY when debug_events=True)
        if debug_events:
            self._insert_events(run_id, df_ev)

        # 7. Compute and insert summary
        self._insert_summary(run_id, df_ts, resolved)

        # 8. Calculate and insert OEE (from state_summary if available)
        self._insert_machine_oee(
            run_id, df_ev, resolved, df_state_summary=df_state_summary
        )

        # 9. Snapshot equipment config
        self._insert_equipment(run_id, resolved)

        # Update completed_at
        self.conn.execute(
            "UPDATE simulation_runs SET completed_at = ? WHERE run_id = ?",
            [datetime.now(), run_id],
        )

        return run_id

    def _insert_simulation_run(self, resolved: "ResolvedConfig") -> int:
        """Insert parent record and return run_id."""
        config_json = self._config_to_json(resolved)
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]

        run_id = self.conn.execute(
            "SELECT nextval('seq_simulation_runs_id')"
        ).fetchone()[0]

        self.conn.execute(
            """
            INSERT INTO simulation_runs (
                run_id, run_name, scenario_name, config_hash, started_at,
                duration_hours, random_seed, telemetry_interval_sec,
                sku_name, sku_description, material_cost_per_pallet,
                selling_price_per_pallet, config_snapshot, simpy_demo_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                run_id,
                resolved.run.name,
                resolved.scenario.name,
                config_hash,
                resolved.run.start_time or datetime.now(),
                resolved.run.duration_hours,
                resolved.run.random_seed,
                resolved.run.telemetry_interval_sec,
                resolved.product.name if resolved.product else None,
                resolved.product.description if resolved.product else None,
                resolved.product.material_cost if resolved.product else None,
                resolved.product.selling_price if resolved.product else None,
                config_json,
                __version__,
            ],
        )
        return run_id

    def _config_to_json(self, resolved: "ResolvedConfig") -> str:
        """Convert resolved config to JSON for storage."""
        snapshot: Dict[str, Any] = {
            "run": {
                "name": resolved.run.name,
                "scenario": resolved.run.scenario,
                "product": resolved.run.product,
                "duration_hours": resolved.run.duration_hours,
                "random_seed": resolved.run.random_seed,
                "telemetry_interval_sec": resolved.run.telemetry_interval_sec,
                "start_time": (
                    resolved.run.start_time.isoformat()
                    if resolved.run.start_time
                    else None
                ),
            },
            "scenario": {
                "name": resolved.scenario.name,
                "topology": resolved.scenario.topology,
                "equipment": resolved.scenario.equipment,
                "overrides": resolved.scenario.overrides,
                "behavior": resolved.scenario.behavior,
            },
            "topology": {
                "name": resolved.topology.name,
                "source": resolved.topology.source,
                "stations": [
                    {
                        "name": s.name,
                        "batch_in": s.batch_in,
                        "output_type": s.output_type.value,
                    }
                    for s in resolved.topology.stations
                ],
                "nodes": [
                    {
                        "name": n.name,
                        "batch_in": n.batch_in,
                        "output_type": n.output_type.value,
                        "equipment_ref": n.equipment_ref,
                        "behavior_ref": n.behavior_ref,
                    }
                    for n in resolved.topology.nodes
                ],
            },
            "equipment": {
                name: {
                    "name": eq.name,
                    "uph": eq.uph,
                    "buffer_capacity": eq.buffer_capacity,
                    "reliability": (
                        {
                            "mtbf_min": eq.reliability.mtbf_min,
                            "mttr_min": eq.reliability.mttr_min,
                        }
                        if eq.reliability
                        else None
                    ),
                    "performance": (
                        {
                            "jam_prob": eq.performance.jam_prob,
                            "jam_time_sec": eq.performance.jam_time_sec,
                        }
                        if eq.performance
                        else None
                    ),
                    "quality": (
                        {
                            "defect_rate": eq.quality.defect_rate,
                            "detection_prob": eq.quality.detection_prob,
                        }
                        if eq.quality
                        else None
                    ),
                    "cost_rates": (
                        {
                            "labor_per_hour": eq.cost_rates.labor_per_hour,
                            "energy_per_hour": eq.cost_rates.energy_per_hour,
                            "overhead_per_hour": eq.cost_rates.overhead_per_hour,
                        }
                        if eq.cost_rates
                        else None
                    ),
                }
                for name, eq in resolved.equipment.items()
            },
            "product": (
                {
                    "name": resolved.product.name,
                    "description": resolved.product.description,
                    "size_oz": resolved.product.size_oz,
                    "units_per_case": resolved.product.units_per_case,
                    "cases_per_pallet": resolved.product.cases_per_pallet,
                    "material_cost": resolved.product.material_cost,
                    "selling_price": resolved.product.selling_price,
                }
                if resolved.product
                else None
            ),
        }
        return json.dumps(snapshot, default=str)

    def _insert_telemetry(self, run_id: int, df_ts: pd.DataFrame) -> None:
        """Insert telemetry records using bulk insert.

        Note: Machine states and buffer levels are stored in machine_telemetry
        (normalized) rather than as JSON blobs here. This leverages DuckDB's
        columnar storage for efficient analytical queries.
        """
        if df_ts.empty:
            return

        # Prepare DataFrame for bulk insert (production + economics only)
        df_insert = pd.DataFrame(
            {
                "ts": df_ts["datetime"].fillna(datetime.now()),
                "sim_time_sec": df_ts["time"].fillna(0),
                "tubes_produced": df_ts.get(
                    "tubes_produced", pd.Series([0] * len(df_ts))
                )
                .fillna(0)
                .astype(int),
                "cases_produced": df_ts.get(
                    "cases_produced", pd.Series([0] * len(df_ts))
                )
                .fillna(0)
                .astype(int),
                "pallets_produced": df_ts.get(
                    "pallets_produced", pd.Series([0] * len(df_ts))
                )
                .fillna(0)
                .astype(int),
                "good_pallets": df_ts.get("good_pallets", pd.Series([0] * len(df_ts)))
                .fillna(0)
                .astype(int),
                "defective_pallets": df_ts.get(
                    "defective_pallets", pd.Series([0] * len(df_ts))
                )
                .fillna(0)
                .astype(int),
                "defects_created": df_ts.get(
                    "defects_created", pd.Series([0] * len(df_ts))
                )
                .fillna(0)
                .astype(int),
                "defects_detected": df_ts.get(
                    "defects_detected", pd.Series([0] * len(df_ts))
                )
                .fillna(0)
                .astype(int),
                "material_cost": df_ts.get(
                    "material_cost", pd.Series([0.0] * len(df_ts))
                ).fillna(0.0),
                "conversion_cost": df_ts.get(
                    "conversion_cost", pd.Series([0.0] * len(df_ts))
                ).fillna(0.0),
                "revenue": df_ts.get("revenue", pd.Series([0.0] * len(df_ts))).fillna(
                    0.0
                ),
                "gross_margin": df_ts.get(
                    "gross_margin", pd.Series([0.0] * len(df_ts))
                ).fillna(0.0),
            }
        )

        # Generate unique IDs based on current max + 1
        max_id_result = self.conn.execute(
            "SELECT COALESCE(MAX(id), 0) FROM telemetry"
        ).fetchone()
        start_id = max_id_result[0] + 1
        df_insert["id"] = range(start_id, start_id + len(df_insert))
        df_insert["run_id"] = run_id

        # Register DataFrame and bulk insert
        self.conn.register("telemetry_df", df_insert)
        self.conn.execute(
            """
            INSERT INTO telemetry (
                id, run_id, ts, sim_time_sec,
                tubes_produced, cases_produced, pallets_produced,
                good_pallets, defective_pallets, defects_created, defects_detected,
                material_cost, conversion_cost, revenue, gross_margin
            )
            SELECT id, run_id, ts, sim_time_sec,
                tubes_produced, cases_produced, pallets_produced,
                good_pallets, defective_pallets, defects_created, defects_detected,
                material_cost, conversion_cost, revenue, gross_margin
            FROM telemetry_df
            """
        )
        self.conn.unregister("telemetry_df")

    def _insert_machine_telemetry(self, run_id: int, df_ts: pd.DataFrame) -> None:
        """Insert per-machine telemetry records using bulk insert."""
        if df_ts.empty:
            return

        # Find machine state columns to determine machine names
        machine_state_cols = [c for c in df_ts.columns if c.endswith("_state")]
        machine_names = [c.replace("_state", "") for c in machine_state_cols]

        if not machine_names:
            return

        # Build expanded DataFrame (one row per machine per timestamp)
        rows = []
        for machine_name in machine_names:
            machine_df = pd.DataFrame(
                {
                    "ts": df_ts["datetime"].fillna(datetime.now()),
                    "sim_time_sec": df_ts["time"].fillna(0),
                    "machine_name": machine_name,
                    "state": df_ts.get(
                        f"{machine_name}_state", pd.Series(["UNKNOWN"] * len(df_ts))
                    ).fillna("UNKNOWN"),
                    "output_count": df_ts.get(
                        f"{machine_name}_output", pd.Series([0] * len(df_ts))
                    )
                    .fillna(0)
                    .astype(int),
                    "buffer_level": df_ts.get(
                        f"Buf_{machine_name}_level", pd.Series([None] * len(df_ts))
                    ),
                    "buffer_capacity": df_ts.get(
                        f"Buf_{machine_name}_cap", pd.Series([None] * len(df_ts))
                    ),
                }
            )
            rows.append(machine_df)

        df_insert = pd.concat(rows, ignore_index=True)

        # Generate unique IDs based on current max + 1
        max_id_result = self.conn.execute(
            "SELECT COALESCE(MAX(id), 0) FROM machine_telemetry"
        ).fetchone()
        start_id = max_id_result[0] + 1
        df_insert["id"] = range(start_id, start_id + len(df_insert))
        df_insert["run_id"] = run_id

        # Register DataFrame and bulk insert
        self.conn.register("machine_telemetry_df", df_insert)
        self.conn.execute(
            """
            INSERT INTO machine_telemetry (
                id, run_id, ts, sim_time_sec, machine_name, state,
                output_count, buffer_level, buffer_capacity
            )
            SELECT id, run_id, ts, sim_time_sec, machine_name, state,
                output_count, buffer_level, buffer_capacity
            FROM machine_telemetry_df
            """
        )
        self.conn.unregister("machine_telemetry_df")

    def _insert_events(self, run_id: int, df_ev: pd.DataFrame) -> None:
        """Insert event records using bulk insert."""
        if df_ev.empty:
            return

        # Calculate duration for each event
        df_work = df_ev.copy()
        df_work["next_time"] = df_work.groupby("machine")["timestamp"].shift(-1)
        df_work["duration_sec"] = df_work["next_time"] - df_work["timestamp"]

        # Prepare DataFrame for bulk insert
        df_insert = pd.DataFrame(
            {
                "ts": df_work["datetime"].fillna(datetime.now()),
                "sim_time_sec": df_work["timestamp"].fillna(0),
                "machine_name": df_work["machine"].fillna("UNKNOWN"),
                "state": df_work["state"].fillna("UNKNOWN"),
                "event_type": df_work["event_type"].fillna("state_change"),
                "duration_sec": df_work["duration_sec"],
            }
        )

        # Generate unique IDs based on current max + 1
        max_id_result = self.conn.execute(
            "SELECT COALESCE(MAX(id), 0) FROM events"
        ).fetchone()
        start_id = max_id_result[0] + 1
        df_insert["id"] = range(start_id, start_id + len(df_insert))
        df_insert["run_id"] = run_id

        # Register DataFrame and bulk insert
        self.conn.register("events_df", df_insert)
        self.conn.execute(
            """
            INSERT INTO events (id, run_id, ts, sim_time_sec, machine_name, state, event_type, duration_sec)
            SELECT id, run_id, ts, sim_time_sec, machine_name, state, event_type, duration_sec
            FROM events_df
            """
        )
        self.conn.unregister("events_df")

    def _insert_state_summary(self, run_id: int, df_summary: pd.DataFrame) -> None:
        """Insert state summary records using bulk insert.

        Args:
            run_id: The simulation run ID
            df_summary: DataFrame from EventAggregator.get_summary_df()
        """
        if df_summary.empty:
            return

        # Prepare DataFrame for bulk insert
        df_insert = df_summary.copy()
        df_insert["run_id"] = run_id

        # Generate unique IDs based on current max + 1
        max_id_result = self.conn.execute(
            "SELECT COALESCE(MAX(id), 0) FROM state_summary"
        ).fetchone()
        start_id = max_id_result[0] + 1
        df_insert["id"] = range(start_id, start_id + len(df_insert))

        # Register DataFrame and bulk insert
        self.conn.register("state_summary_df", df_insert)
        self.conn.execute(
            """
            INSERT INTO state_summary (
                id, run_id, bucket_start_ts, bucket_index, machine_name,
                execute_sec, starved_sec, blocked_sec, down_sec, jammed_sec,
                transition_count, down_count, jammed_count, availability_pct
            )
            SELECT id, run_id, bucket_start_ts, bucket_index, machine_name,
                execute_sec, starved_sec, blocked_sec, down_sec, jammed_sec,
                transition_count, down_count, jammed_count, availability_pct
            FROM state_summary_df
            """
        )
        self.conn.unregister("state_summary_df")

    def _insert_events_detail(self, run_id: int, df_detail: pd.DataFrame) -> None:
        """Insert events detail records using bulk insert.

        Args:
            run_id: The simulation run ID
            df_detail: DataFrame from EventAggregator.get_detail_df()
        """
        if df_detail.empty:
            return

        # Prepare DataFrame for bulk insert
        df_insert = df_detail.copy()
        df_insert["run_id"] = run_id

        # Generate unique IDs based on current max + 1
        max_id_result = self.conn.execute(
            "SELECT COALESCE(MAX(id), 0) FROM events_detail"
        ).fetchone()
        start_id = max_id_result[0] + 1
        df_insert["id"] = range(start_id, start_id + len(df_insert))

        # Register DataFrame and bulk insert
        self.conn.register("events_detail_df", df_insert)
        self.conn.execute(
            """
            INSERT INTO events_detail (
                id, run_id, ts, sim_time_sec, machine_name,
                state, prev_state, duration_sec, is_interesting
            )
            SELECT id, run_id, ts, sim_time_sec, machine_name,
                state, prev_state, duration_sec, is_interesting
            FROM events_detail_df
            """
        )
        self.conn.unregister("events_detail_df")

    def _insert_summary(
        self,
        run_id: int,
        df_ts: pd.DataFrame,
        resolved: "ResolvedConfig",
    ) -> None:
        """Insert run summary with aggregated metrics."""
        if df_ts.empty:
            self.conn.execute(
                "INSERT INTO run_summary (run_id) VALUES (?)",
                [run_id],
            )
            return

        total_tubes = int(df_ts.get("tubes_produced", pd.Series([0])).sum())
        total_cases = int(df_ts.get("cases_produced", pd.Series([0])).sum())
        total_pallets = int(df_ts.get("pallets_produced", pd.Series([0])).sum())
        total_good = int(df_ts.get("good_pallets", pd.Series([0])).sum())
        total_defective = int(df_ts.get("defective_pallets", pd.Series([0])).sum())

        total_revenue = float(df_ts.get("revenue", pd.Series([0])).sum())
        total_material = float(df_ts.get("material_cost", pd.Series([0])).sum())
        total_conversion = float(df_ts.get("conversion_cost", pd.Series([0])).sum())
        total_margin = float(df_ts.get("gross_margin", pd.Series([0])).sum())

        margin_pct = (total_margin / total_revenue * 100) if total_revenue > 0 else None
        yield_pct = (total_good / total_pallets * 100) if total_pallets > 0 else None
        throughput = (
            total_pallets / resolved.run.duration_hours if total_pallets > 0 else 0
        )

        self.conn.execute(
            """
            INSERT INTO run_summary (
                run_id, total_tubes, total_cases, total_pallets,
                total_good_pallets, total_defective_pallets,
                total_revenue, total_material_cost, total_conversion_cost,
                total_gross_margin, margin_percent, yield_percent, throughput_per_hour
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                run_id,
                total_tubes,
                total_cases,
                total_pallets,
                total_good,
                total_defective,
                total_revenue,
                total_material,
                total_conversion,
                total_margin,
                margin_pct,
                yield_pct,
                throughput,
            ],
        )

    def _insert_machine_oee(
        self,
        run_id: int,
        df_ev: pd.DataFrame,
        resolved: "ResolvedConfig",
        *,
        df_state_summary: Optional[pd.DataFrame] = None,
    ) -> None:
        """Calculate and insert OEE metrics per machine.

        Uses state_summary (pre-aggregated) when available for efficiency,
        falls back to computing from df_ev for backwards compatibility.
        """
        total_time_sec = resolved.run.duration_hours * 3600

        # Prefer state_summary for OEE calculation (much more efficient)
        if df_state_summary is not None and not df_state_summary.empty:
            self._insert_machine_oee_from_summary(
                run_id, df_state_summary, total_time_sec
            )
        elif not df_ev.empty:
            # Fallback: compute from full events (backwards compatibility)
            self._insert_machine_oee_from_events(run_id, df_ev, total_time_sec)

    def _insert_machine_oee_from_summary(
        self,
        run_id: int,
        df_summary: pd.DataFrame,
        total_time_sec: float,
    ) -> None:
        """Calculate OEE from pre-aggregated state_summary."""
        # Aggregate across all buckets per machine
        machine_stats = (
            df_summary.groupby("machine_name")
            .agg(
                {
                    "execute_sec": "sum",
                    "starved_sec": "sum",
                    "blocked_sec": "sum",
                    "down_sec": "sum",
                    "jammed_sec": "sum",
                }
            )
            .reset_index()
        )

        for _, row in machine_stats.iterrows():
            machine = row["machine_name"]
            execute_time = float(row["execute_sec"])
            starved_time = float(row["starved_sec"])
            blocked_time = float(row["blocked_sec"])
            down_time = float(row["down_sec"])
            jammed_time = float(row["jammed_sec"])

            # Availability = (Total - Down) / Total
            availability = (
                ((total_time_sec - down_time) / total_time_sec * 100)
                if total_time_sec > 0
                else 100
            )

            # Simple OEE = Availability (Performance and Quality need more data)
            oee = availability  # Simplified for now

            oee_id = self.conn.execute(
                "SELECT nextval('seq_machine_oee_id')"
            ).fetchone()[0]

            self.conn.execute(
                """
                INSERT INTO machine_oee (
                    id, run_id, machine_name, total_time_sec,
                    execute_time_sec, starved_time_sec, blocked_time_sec,
                    down_time_sec, jammed_time_sec,
                    availability_percent, oee_percent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    oee_id,
                    run_id,
                    machine,
                    total_time_sec,
                    execute_time,
                    starved_time,
                    blocked_time,
                    down_time,
                    jammed_time,
                    availability,
                    oee,
                ],
            )

    def _insert_machine_oee_from_events(
        self,
        run_id: int,
        df_ev: pd.DataFrame,
        total_time_sec: float,
    ) -> None:
        """Calculate OEE from full events (fallback for backwards compatibility)."""
        # Calculate duration for each event
        df_work = df_ev.copy()
        df_work["next_time"] = df_work.groupby("machine")["timestamp"].shift(-1)
        df_work["duration"] = df_work["next_time"] - df_work["timestamp"]

        # Aggregate by machine and state
        for machine in df_work["machine"].unique():
            machine_events = df_work[df_work["machine"] == machine]

            state_times = machine_events.groupby("state")["duration"].sum()

            execute_time = float(state_times.get("EXECUTE", 0))
            starved_time = float(state_times.get("STARVED", 0))
            blocked_time = float(state_times.get("BLOCKED", 0))
            down_time = float(state_times.get("DOWN", 0))
            jammed_time = float(state_times.get("JAMMED", 0))

            # Availability = (Total - Down) / Total
            availability = (
                ((total_time_sec - down_time) / total_time_sec * 100)
                if total_time_sec > 0
                else 100
            )

            # Simple OEE = Availability (Performance and Quality need more data)
            oee = availability  # Simplified for now

            oee_id = self.conn.execute(
                "SELECT nextval('seq_machine_oee_id')"
            ).fetchone()[0]

            self.conn.execute(
                """
                INSERT INTO machine_oee (
                    id, run_id, machine_name, total_time_sec,
                    execute_time_sec, starved_time_sec, blocked_time_sec,
                    down_time_sec, jammed_time_sec,
                    availability_percent, oee_percent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    oee_id,
                    run_id,
                    machine,
                    total_time_sec,
                    execute_time,
                    starved_time,
                    blocked_time,
                    down_time,
                    jammed_time,
                    availability,
                    oee,
                ],
            )

    def _insert_equipment(self, run_id: int, resolved: "ResolvedConfig") -> None:
        """Insert equipment configuration snapshot."""
        for name, eq in resolved.equipment.items():
            eq_id = self.conn.execute(
                "SELECT nextval('seq_run_equipment_id')"
            ).fetchone()[0]

            reliability = eq.reliability
            performance = eq.performance
            quality = eq.quality

            self.conn.execute(
                """
                INSERT INTO run_equipment (
                    id, run_id, machine_name, uph, buffer_capacity,
                    mtbf_min, mttr_min, jam_prob, jam_time_sec,
                    defect_rate, detection_prob
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    eq_id,
                    run_id,
                    name,
                    eq.uph,
                    eq.buffer_capacity,
                    reliability.mtbf_min if reliability else None,
                    reliability.mttr_min if reliability else None,
                    performance.jam_prob if performance else None,
                    performance.jam_time_sec if performance else None,
                    quality.defect_rate if quality else None,
                    quality.detection_prob if quality else None,
                ],
            )

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()
