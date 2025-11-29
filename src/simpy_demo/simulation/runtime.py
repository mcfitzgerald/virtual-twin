"""Runtime execution for generated scenario bundles."""

from pathlib import Path
from typing import Tuple

import pandas as pd
import yaml

from simpy_demo.engine import SimulationEngine
from simpy_demo.loader import ConfigLoader


def execute_scenario(config_path: Path | str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Execute a scenario from a config_snapshot.yaml file.

    This function is called by generated scenario.py files.

    Args:
        config_path: Path to config_snapshot.yaml

    Returns:
        Tuple of (telemetry_df, events_df)
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config snapshot not found: {config_path}")

    # Load config snapshot
    with open(config_path) as f:
        config_data = yaml.safe_load(f)

    # Extract metadata
    meta = config_data.get("_meta", {})
    run_name = meta.get("run_name")
    config_dir = meta.get("config_dir", "config")

    if not run_name:
        raise ValueError("Config snapshot missing _meta.run_name")

    print(f"Executing scenario: {run_name}")
    print(f"  Config dir: {config_dir}")
    print(f"  Generated: {meta.get('generated_at', 'unknown')}")

    # Load and run using the original config directory
    # The snapshot is for auditing; we use original configs for reproducibility
    loader = ConfigLoader(config_dir)
    resolved = loader.resolve_run(run_name)

    # Run simulation
    engine = SimulationEngine(config_dir)
    df_ts, df_ev = engine.run_resolved(resolved)

    # Print summary
    _print_summary(df_ts, df_ev, resolved)

    return df_ts, df_ev


def _print_summary(df_ts: pd.DataFrame, df_ev: pd.DataFrame, resolved) -> None:
    """Print execution summary."""
    print("\n--- SIMULATION COMPLETE ---")
    print(f"Telemetry Records: {len(df_ts)}")
    print(f"Event Records: {len(df_ev)}")

    if not df_ts.empty:
        print("\n--- PRODUCTION SUMMARY ---")
        if "tubes_produced" in df_ts.columns:
            print(f"Tubes Produced:    {int(df_ts['tubes_produced'].sum()):,}")
        if "cases_produced" in df_ts.columns:
            print(f"Cases Produced:    {int(df_ts['cases_produced'].sum()):,}")
        if "pallets_produced" in df_ts.columns:
            print(f"Pallets Produced:  {int(df_ts['pallets_produced'].sum()):,}")
        if "good_pallets" in df_ts.columns:
            print(f"  Good Pallets:    {int(df_ts['good_pallets'].sum()):,}")
        if "defective_pallets" in df_ts.columns:
            print(f"  Defective:       {int(df_ts['defective_pallets'].sum()):,}")

        # Economic Summary
        if "revenue" in df_ts.columns:
            last = df_ts.iloc[-1]
            if "sku_name" in df_ts.columns and pd.notna(last.get("sku_name")):
                print("\n--- ECONOMIC SUMMARY ---")
                print(f"Product: {last['sku_name']}")
                if last.get("sku_description"):
                    print(f"         {last['sku_description']}")

                revenue = df_ts["revenue"].sum()
                material = df_ts["material_cost"].sum()
                conversion = df_ts["conversion_cost"].sum()
                margin = df_ts["gross_margin"].sum()

                print(f"\nRevenue:          ${revenue:,.2f}")
                print(f"Material Cost:    ${material:,.2f}")
                print(f"Conversion Cost:  ${conversion:,.2f}")
                print(f"{'─' * 30}")
                print(f"Gross Margin:     ${margin:,.2f}")
                if revenue > 0:
                    margin_pct = (margin / revenue) * 100
                    print(f"Margin %:         {margin_pct:.1f}%")
