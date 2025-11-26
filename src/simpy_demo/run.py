"""Entry point for running simulations."""

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

from simpy_demo.engine import SimulationEngine


def run_simulation(
    run_name: str = "baseline_8hr", config_dir: str = "config"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run a simulation with the given run config name.

    Args:
        run_name: Name of the run config (without .yaml extension)
        config_dir: Path to config directory

    Returns:
        Tuple of (telemetry_df, events_df)
    """
    engine = SimulationEngine(config_dir)
    df_ts, df_ev = engine.run(run_name)

    # Report
    print("\n--- SIMULATION COMPLETE ---")
    print(f"Telemetry Records: {len(df_ts)}")
    print(f"Event Records: {len(df_ev)}")

    # Production Summary (sum of incremental values)
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
        if "defects_created" in df_ts.columns:
            print(f"Defects Created:   {int(df_ts['defects_created'].sum()):,}")
        if "defects_detected" in df_ts.columns:
            print(f"Defects Detected:  {int(df_ts['defects_detected'].sum()):,}")

        # Economic Summary (sum of incremental values)
        last = df_ts.iloc[-1]
        if "sku_name" in df_ts.columns and pd.notna(last.get("sku_name")):
            print("\n--- ECONOMIC SUMMARY ---")
            print(f"Product: {last['sku_name']}")
            if last.get("sku_description"):
                print(f"         {last['sku_description']}")

            good = int(df_ts["good_pallets"].sum())
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
            if good > 0:
                cost_per_pallet = (material + conversion) / good
                print(f"Cost per Pallet:  ${cost_per_pallet:,.2f}")

    # OEE Analysis
    print("\n--- Time in State (Seconds) ---")
    if not df_ev.empty:
        # Calculate duration of each state
        df_ev["next_time"] = df_ev.groupby("machine")["timestamp"].shift(-1)
        df_ev["duration"] = df_ev["next_time"] - df_ev["timestamp"]

        # Pivot table for summary
        stats = df_ev.groupby(["machine", "state"])["duration"].sum().unstack().fillna(0)

        # Get duration from resolved config
        resolved = engine.loader.resolve_run(run_name)
        total_time = resolved.run.duration_hours * 3600

        # Calculate Availability (Total - Down / Total)
        stats["Availability_%"] = (1 - (stats.get("DOWN", 0) / total_time)) * 100

        # Reorder columns for readability
        cols = ["EXECUTE", "STARVED", "BLOCKED", "DOWN", "JAMMED", "Availability_%"]
        existing_cols = [c for c in cols if c in stats.columns]
        print(stats[existing_cols].round(1))

    return df_ts, df_ev


def main():
    """CLI entry point for running simulations."""
    parser = argparse.ArgumentParser(
        description="Run SimPy production line simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m simpy_demo                              # Run default baseline_8hr
  python -m simpy_demo --run baseline_8hr           # Run specific config
  python -m simpy_demo --run baseline_8hr --export  # Export to CSV
  python -m simpy_demo --config ./my_configs        # Use custom config dir
        """,
    )
    parser.add_argument(
        "--run",
        default="baseline_8hr",
        help="Run config name (default: baseline_8hr)",
    )
    parser.add_argument(
        "--config",
        default="config",
        help="Config directory path (default: config)",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export results to CSV files",
    )
    parser.add_argument(
        "--output",
        default="output",
        help="Output directory for CSV export (default: output)",
    )

    args = parser.parse_args()

    # Run simulation
    df_ts, df_ev = run_simulation(args.run, args.config)

    # Export if requested (datetime already embedded during simulation)
    if args.export:
        # Create output directory
        output_dir = Path(args.output)
        output_dir.mkdir(exist_ok=True)

        # Generate timestamped filenames from first telemetry record
        if "datetime" in df_ts.columns and df_ts["datetime"].iloc[0]:
            timestamp = df_ts["datetime"].iloc[0].strftime("%Y%m%d_%H%M%S")
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        ts_path = output_dir / f"telemetry_{timestamp}.csv"
        ev_path = output_dir / f"events_{timestamp}.csv"

        # Export to CSV
        df_ts.to_csv(ts_path, index=False)
        df_ev.to_csv(ev_path, index=False)

        print(f"\nExported: {ts_path} ({len(df_ts)} rows)")
        print(f"Exported: {ev_path} ({len(df_ev)} rows)")


if __name__ == "__main__":
    main()
