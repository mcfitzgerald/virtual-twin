"""Simulate command: Run a scenario bundle and generate output."""

import json
from datetime import datetime
from pathlib import Path
from typing import Tuple

import pandas as pd
import yaml

from virtual_twin.engine import SimulationEngine
from virtual_twin.loader import ConfigLoader


def simulate(
    scenario_path: str,
    export: bool = True,
    save_to_db: bool = True,
    db_path: str | None = None,
    debug_events: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame, Path]:
    """Run a scenario bundle and generate output.

    Args:
        scenario_path: Path to the scenario bundle directory
        export: If True, export results to CSV files in the bundle's output/ dir
        save_to_db: If True, save results to DuckDB database
        db_path: Custom path for DuckDB file
        debug_events: If True, also populate full events table for debugging

    Returns:
        Tuple of (telemetry_df, events_df, output_dir)
    """
    bundle_dir = Path(scenario_path)

    # Validate bundle structure
    config_snapshot = bundle_dir / "config_snapshot.yaml"
    metadata_file = bundle_dir / "metadata.json"

    if not bundle_dir.exists():
        raise FileNotFoundError(f"Scenario bundle not found: {bundle_dir}")
    if not config_snapshot.exists():
        raise FileNotFoundError(f"Config snapshot not found: {config_snapshot}")
    if not metadata_file.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_file}")

    # Load metadata
    with open(metadata_file) as f:
        metadata = json.load(f)

    print(f"Running scenario: {metadata['scenario_name']}")
    print(f"  Generated: {metadata['generated_at']}")
    print(f"  Config hash: {metadata['config_hash'][:16]}...")

    # Load config snapshot
    with open(config_snapshot) as f:
        config_data = yaml.safe_load(f)

    # Create a temporary config loader that uses the snapshot
    # We need to reconstruct the resolved config from the snapshot
    run_name = config_data["_meta"]["run_name"]
    config_dir = config_data["_meta"].get("config_dir", "config")

    # Use the original config dir to load and run
    # The snapshot is for auditing; we run from original configs for now
    # Future enhancement: support running purely from snapshot
    loader = ConfigLoader(config_dir)
    resolved = loader.resolve_run(run_name)

    # Run simulation
    engine = SimulationEngine(config_dir, save_to_db=save_to_db, db_path=db_path)
    df_ts, df_ev, _, _ = engine.run_resolved(resolved, debug_events=debug_events)

    # Create output directory in bundle
    output_dir = bundle_dir / "output"
    output_dir.mkdir(exist_ok=True)

    if export:
        # Generate timestamped filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        ts_path = output_dir / f"telemetry_{timestamp}.csv"
        ev_path = output_dir / f"events_{timestamp}.csv"
        summary_path = output_dir / f"summary_{timestamp}.json"

        # Export CSVs
        df_ts.to_csv(ts_path, index=False)
        df_ev.to_csv(ev_path, index=False)

        # Generate summary
        summary = _generate_summary(df_ts, df_ev, resolved, metadata)
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2, default=str)

        print(f"\nExported to {output_dir}:")
        print(f"  telemetry_{timestamp}.csv ({len(df_ts)} rows)")
        print(f"  events_{timestamp}.csv ({len(df_ev)} rows)")
        print(f"  summary_{timestamp}.json")

    return df_ts, df_ev, output_dir


def _generate_summary(
    df_ts: pd.DataFrame,
    df_ev: pd.DataFrame,
    resolved,
    metadata: dict,
) -> dict:
    """Generate a summary JSON with OEE and economics."""
    summary = {
        "scenario": metadata["scenario_name"],
        "generated_at": metadata["generated_at"],
        "simulation_completed_at": datetime.now().isoformat(),
        "config_hash": metadata["config_hash"],
    }

    # Production summary
    if not df_ts.empty:
        summary["production"] = {
            "tubes_produced": int(df_ts.get("tubes_produced", pd.Series([0])).sum()),
            "cases_produced": int(df_ts.get("cases_produced", pd.Series([0])).sum()),
            "pallets_produced": int(df_ts.get("pallets_produced", pd.Series([0])).sum()),
            "good_pallets": int(df_ts.get("good_pallets", pd.Series([0])).sum()),
            "defective_pallets": int(df_ts.get("defective_pallets", pd.Series([0])).sum()),
            "defects_created": int(df_ts.get("defects_created", pd.Series([0])).sum()),
            "defects_detected": int(df_ts.get("defects_detected", pd.Series([0])).sum()),
        }

        # Economic summary
        if "revenue" in df_ts.columns:
            summary["economics"] = {
                "revenue": round(df_ts["revenue"].sum(), 2),
                "material_cost": round(df_ts["material_cost"].sum(), 2),
                "conversion_cost": round(df_ts["conversion_cost"].sum(), 2),
                "gross_margin": round(df_ts["gross_margin"].sum(), 2),
            }
            if summary["economics"]["revenue"] > 0:
                summary["economics"]["margin_percent"] = round(
                    summary["economics"]["gross_margin"]
                    / summary["economics"]["revenue"]
                    * 100,
                    1,
                )

    # OEE summary from events
    if not df_ev.empty:
        total_time = resolved.run.duration_hours * 3600
        df_ev["next_time"] = df_ev.groupby("machine")["timestamp"].shift(-1)
        df_ev["duration"] = df_ev["next_time"] - df_ev["timestamp"]

        oee_by_machine = {}
        for machine in df_ev["machine"].unique():
            machine_events = df_ev[df_ev["machine"] == machine]
            down_time = machine_events[machine_events["state"] == "DOWN"]["duration"].sum()
            availability = (1 - down_time / total_time) * 100 if total_time > 0 else 100
            oee_by_machine[machine] = {
                "availability_percent": round(availability, 1),
                "down_time_sec": round(down_time, 1) if pd.notna(down_time) else 0,
            }
        summary["oee"] = oee_by_machine

    return summary
