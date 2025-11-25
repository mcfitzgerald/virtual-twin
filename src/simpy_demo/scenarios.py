from simpy_demo.models import ScenarioConfig, MachineConfig, MaterialType
from simpy_demo.simulation import ProductionLine


def get_default_scenario() -> ScenarioConfig:
    """Default scenario based on White Paper: Cosmetics line with microstops."""
    return ScenarioConfig(
        name="Cosmetics_Line_Microstops",
        duration_hours=8.0,
        layout=[
            # 1. Depalletizer: Pushes tubes into the line
            MachineConfig(
                name="Depalletizer",
                uph=11000,
                batch_in=1,
                output_type=MaterialType.TUBE,
                buffer_capacity=1000,
                mtbf_min=480,  # Very reliable (once per shift)
            ),
            # 2. Filler: The Bottleneck & Quality Risk
            MachineConfig(
                name="Filler",
                uph=10000,
                batch_in=1,
                output_type=MaterialType.TUBE,
                buffer_capacity=50,  # Small buffer = High starvation risk
                mtbf_min=120,  # Major breakdown every 2 hours
                mttr_min=15,  # Takes 15 mins to fix
                jam_prob=0.01,  # 1% chance of microstop per tube
                jam_time_sec=15,  # 15 seconds to clear jam
                defect_rate=0.02,  # 2% defects
            ),
            # 3. Checkweigher: Inspection Station
            MachineConfig(
                name="Inspector",
                uph=11000,
                batch_in=1,
                buffer_capacity=20,  # Minimal accumulation
                detection_prob=0.95,  # Catches 95% of defects
            ),
            # 4. Packer: Aggregation (12 -> 1)
            MachineConfig(
                name="Packer",
                uph=12000,
                batch_in=12,
                output_type=MaterialType.CASE,
                buffer_capacity=100,  # Accumulator table
                mtbf_min=240,
                jam_prob=0.05,  # 5% chance of jam per BOX (not tube)
                jam_time_sec=30,
            ),
            # 5. Palletizer: End of Line (60 -> 1)
            MachineConfig(
                name="Palletizer",
                uph=13000,
                batch_in=60,
                output_type=MaterialType.PALLET,
                buffer_capacity=40,
                mtbf_min=480,
            ),
        ],
    )


def run_simulation(scenario: ScenarioConfig | None = None):
    """Run a simulation with the given scenario (or default)."""
    if scenario is None:
        scenario = get_default_scenario()

    sim = ProductionLine(scenario)
    df_ts, df_ev = sim.run()

    # --- Report ---
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
    run_simulation()


if __name__ == "__main__":
    main()
