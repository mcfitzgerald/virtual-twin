"""Entry point for running simulations."""

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

from simpy_demo.cli.configure import configure as configure_func
from simpy_demo.cli.simulate import simulate as simulate_func
from simpy_demo.engine import SimulationEngine


def run_simulation(
    run_name: str = "baseline_8hr",
    config_dir: str = "config",
    save_to_db: bool = True,
    db_path: str | None = None,
    debug_events: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run a simulation with the given run config name.

    Args:
        run_name: Name of the run config (without .yaml extension)
        config_dir: Path to config directory
        save_to_db: If True, save results to DuckDB database
        db_path: Custom path for DuckDB file
        debug_events: If True, also populate full events table for debugging

    Returns:
        Tuple of (telemetry_df, events_df)
    """
    engine = SimulationEngine(config_dir, save_to_db=save_to_db, db_path=db_path)
    df_ts, df_ev, _, _ = engine.run(run_name, debug_events=debug_events)

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


def _run_command(args: argparse.Namespace) -> None:
    """Handle 'run' subcommand (combined configure+simulate)."""
    # Determine db save settings
    save_to_db = not getattr(args, "no_db", False)
    db_path = getattr(args, "db_path", None)
    debug_events = getattr(args, "debug_events", False)

    # Run simulation
    df_ts, df_ev = run_simulation(args.run, args.config, save_to_db, db_path, debug_events)

    # Export if requested
    if args.export:
        output_dir = Path(args.output)
        output_dir.mkdir(exist_ok=True)

        # Generate timestamped filenames
        if "datetime" in df_ts.columns and df_ts["datetime"].iloc[0]:
            timestamp = df_ts["datetime"].iloc[0].strftime("%Y%m%d_%H%M%S")
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        ts_path = output_dir / f"telemetry_{timestamp}.csv"
        ev_path = output_dir / f"events_{timestamp}.csv"

        df_ts.to_csv(ts_path, index=False)
        df_ev.to_csv(ev_path, index=False)

        print(f"\nExported: {ts_path} ({len(df_ts)} rows)")
        print(f"Exported: {ev_path} ({len(df_ev)} rows)")


def _configure_command(args: argparse.Namespace) -> None:
    """Handle 'configure' subcommand."""
    configure_func(
        run_name=args.run,
        config_dir=args.config,
        output_dir=args.output,
        dry_run=args.dry_run,
    )


def _simulate_command(args: argparse.Namespace) -> None:
    """Handle 'simulate' subcommand."""
    save_to_db = not getattr(args, "no_db", False)
    db_path = getattr(args, "db_path", None)
    debug_events = getattr(args, "debug_events", False)

    simulate_func(
        scenario_path=args.scenario,
        export=args.export,
        save_to_db=save_to_db,
        db_path=db_path,
        debug_events=debug_events,
    )


def main():
    """CLI entry point with subcommands."""
    import sys

    # Check if first arg is a subcommand or starts with -- (but not --help/-h)
    # This enables backward compatibility: python -m simpy_demo --run baseline_8hr
    if (
        len(sys.argv) > 1
        and sys.argv[1].startswith("--")
        and sys.argv[1] not in ("--help", "-h")
    ):
        # Legacy mode: no subcommand, use --run directly
        compat_parser = argparse.ArgumentParser(
            description="SimPy production line simulation (legacy mode)",
        )
        compat_parser.add_argument("--run", default="baseline_8hr")
        compat_parser.add_argument("--config", default="config")
        compat_parser.add_argument("--export", action="store_true")
        compat_parser.add_argument("--output", default="output")
        compat_parser.add_argument(
            "--no-db", action="store_true", help="Skip saving to DuckDB database"
        )
        compat_parser.add_argument(
            "--db-path", default=None, help="Custom path for DuckDB file"
        )
        compat_parser.add_argument(
            "--debug-events",
            action="store_true",
            help="Enable full event logging for debugging (increases storage)",
        )
        compat_args = compat_parser.parse_args()
        _run_command(compat_args)
        return

    # Modern mode: use subcommands
    parser = argparse.ArgumentParser(
        description="SimPy production line simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  run         Run a simulation directly from config (default behavior)
  configure   Generate a scenario bundle from config
  simulate    Run a scenario bundle

Examples:
  # Run simulation directly (existing behavior)
  python -m simpy_demo run --run baseline_8hr
  python -m simpy_demo --run baseline_8hr  # shorthand (legacy mode)

  # Generate scenario bundle, then run it
  python -m simpy_demo configure --run baseline_8hr
  python -m simpy_demo simulate --scenario scenarios/baseline_8hr_20250126_143022

  # Combined with export
  python -m simpy_demo run --run baseline_8hr --export
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # === 'run' subcommand (default behavior) ===
    run_parser = subparsers.add_parser(
        "run",
        help="Run simulation directly from config",
        description="Run a simulation directly from YAML configuration files.",
    )
    run_parser.add_argument(
        "--run",
        default="baseline_8hr",
        help="Run config name (default: baseline_8hr)",
    )
    run_parser.add_argument(
        "--config",
        default="config",
        help="Config directory path (default: config)",
    )
    run_parser.add_argument(
        "--export",
        action="store_true",
        help="Export results to CSV files",
    )
    run_parser.add_argument(
        "--output",
        default="output",
        help="Output directory for CSV export (default: output)",
    )
    run_parser.add_argument(
        "--no-db",
        action="store_true",
        help="Skip saving to DuckDB database",
    )
    run_parser.add_argument(
        "--db-path",
        default=None,
        help="Custom path for DuckDB file (default: ./simpy_results.duckdb)",
    )
    run_parser.add_argument(
        "--debug-events",
        action="store_true",
        help="Enable full event logging for debugging (increases storage)",
    )
    run_parser.set_defaults(func=_run_command)

    # === 'configure' subcommand ===
    configure_parser = subparsers.add_parser(
        "configure",
        help="Generate a scenario bundle from config",
        description="Generate a standalone scenario bundle from YAML configuration.",
    )
    configure_parser.add_argument(
        "--run",
        required=True,
        help="Run config name (required)",
    )
    configure_parser.add_argument(
        "--config",
        default="config",
        help="Config directory path (default: config)",
    )
    configure_parser.add_argument(
        "--output",
        default="scenarios",
        help="Output directory for scenario bundles (default: scenarios)",
    )
    configure_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config without generating files",
    )
    configure_parser.set_defaults(func=_configure_command)

    # === 'simulate' subcommand ===
    simulate_parser = subparsers.add_parser(
        "simulate",
        help="Run a scenario bundle",
        description="Run a previously generated scenario bundle.",
    )
    simulate_parser.add_argument(
        "--scenario",
        required=True,
        help="Path to scenario bundle directory (required)",
    )
    simulate_parser.add_argument(
        "--export",
        action="store_true",
        default=True,
        help="Export results to bundle's output/ directory (default: True)",
    )
    simulate_parser.add_argument(
        "--no-export",
        action="store_false",
        dest="export",
        help="Skip exporting results",
    )
    simulate_parser.add_argument(
        "--no-db",
        action="store_true",
        help="Skip saving to DuckDB database",
    )
    simulate_parser.add_argument(
        "--db-path",
        default=None,
        help="Custom path for DuckDB file (default: ./simpy_results.duckdb)",
    )
    simulate_parser.add_argument(
        "--debug-events",
        action="store_true",
        help="Enable full event logging for debugging (increases storage)",
    )
    simulate_parser.set_defaults(func=_simulate_command)

    # Parse arguments
    args = parser.parse_args()

    # Handle no subcommand (default to run)
    if args.command is None:
        # Run with defaults
        default_args = argparse.Namespace(
            run="baseline_8hr",
            config="config",
            export=False,
            output="output",
            no_db=False,
            db_path=None,
            debug_events=False,
        )
        _run_command(default_args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
