"""Entry point for running simulations."""

import pandas as pd

from simpy_demo.baseline import BASELINE
from simpy_demo.config import EquipmentParams, ScenarioConfig
from simpy_demo.engine import SimulationEngine
from simpy_demo.topology import CosmeticsLine


def run_simulation(scenario: ScenarioConfig | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run a simulation with the given scenario (or default).

    Args:
        scenario: Scenario configuration. If None, runs baseline with default params.

    Returns:
        Tuple of (telemetry_df, events_df)
    """
    if scenario is None:
        scenario = ScenarioConfig(name="Baseline")

    # Create engine and run
    engine = SimulationEngine(CosmeticsLine, BASELINE)
    df_ts, df_ev = engine.run(scenario)

    # Report
    print("\n--- SIMULATION COMPLETE ---")
    print(f"Telemetry Records: {len(df_ts)}")
    print(f"Event Records: {len(df_ev)}")

    # OEE Analysis
    print("\n--- Time in State (Seconds) ---")
    if not df_ev.empty:
        # Calculate duration of each state
        df_ev["next_time"] = df_ev.groupby("machine")["timestamp"].shift(-1)
        df_ev["duration"] = df_ev["next_time"] - df_ev["timestamp"]

        # Pivot table for summary
        stats = df_ev.groupby(["machine", "state"])["duration"].sum().unstack().fillna(0)

        # Calculate Availability (Total - Down / Total)
        total_time = scenario.duration_hours * 3600
        stats["Availability_%"] = (1 - (stats.get("DOWN", 0) / total_time)) * 100

        # Reorder columns for readability
        cols = ["EXECUTE", "STARVED", "BLOCKED", "DOWN", "JAMMED", "Availability_%"]
        existing_cols = [c for c in cols if c in stats.columns]
        print(stats[existing_cols].round(1))

    return df_ts, df_ev


def main():
    """Entry point for running the default simulation."""
    # Run baseline scenario
    run_simulation()

    # Example: Run a what-if scenario
    # scenario = ScenarioConfig(
    #     name="large_buffer_test",
    #     duration_hours=8.0,
    #     equipment={
    #         "Filler": EquipmentParams(buffer_capacity=500)
    #     }
    # )
    # run_simulation(scenario)


if __name__ == "__main__":
    main()
