"""Manufacturing reality validation tests for simpy-demo.

These tests verify that simulation outputs look like real manufacturing data,
based on industry benchmarks:
- OEE typical: 55-60%, world-class: 85%+
- Availability: 85-95% typical
- Performance: 80-95% typical
- Quality: 95-99% typical

Sources:
- https://www.oee.com/calculating-oee/
- https://shoplogix.com/oee-calculation-in-cpg/
- https://evocon.com/articles/world-class-oee-industry-benchmarks-from-more-than-50-countries/
"""

from typing import Tuple

import pandas as pd
import pytest

from simpy_demo import SimulationEngine


class TestProductionSanity:
    """Basic sanity checks on production counts."""

    def test_production_counts_non_negative(self, telemetry_df: pd.DataFrame):
        """All production counts must be >= 0."""
        production_cols = [
            "tubes_produced",
            "cases_produced",
            "pallets_produced",
            "good_pallets",
            "defective_pallets",
        ]
        for col in production_cols:
            if col in telemetry_df.columns:
                assert (telemetry_df[col] >= 0).all(), f"{col} has negative values"

    def test_good_plus_defective_equals_total(self, telemetry_df: pd.DataFrame):
        """good_pallets + defective_pallets should equal pallets_produced."""
        total_good = telemetry_df["good_pallets"].sum()
        total_defective = telemetry_df["defective_pallets"].sum()
        total_pallets = telemetry_df["pallets_produced"].sum()

        assert total_good + total_defective == total_pallets, (
            f"Accounting mismatch: {total_good} good + {total_defective} defective "
            f"!= {total_pallets} total"
        )


class TestPhysicalLimits:
    """Tests that production respects physical constraints."""

    def test_throughput_within_physical_limits(
        self, engine: SimulationEngine
    ):
        """Production should not exceed theoretical maximum by unreasonable amount."""
        resolved = engine.loader.resolve_run("baseline_8hr")
        # Use longer duration for more meaningful test
        test_duration = 0.5  # 30 minutes
        resolved.run.duration_hours = test_duration

        df_ts, _ = engine.run_resolved(resolved)

        # Filler UPH is 10,000 tubes/hour
        filler_uph = 10000
        max_possible_tubes = filler_uph * test_duration
        actual_tubes = df_ts["tubes_produced"].sum()

        # Allow 20% tolerance for simulation timing variations
        # The discrete event simulation may not align perfectly with wall clock
        assert actual_tubes <= max_possible_tubes * 1.20, (
            f"Produced {actual_tubes} tubes exceeds max {max_possible_tubes} by >20%"
        )

        # Also verify we're producing a reasonable amount (not zero or near zero)
        assert actual_tubes >= max_possible_tubes * 0.50, (
            f"Produced only {actual_tubes} tubes, expected at least 50% of max {max_possible_tubes}"
        )

    def test_buffer_levels_within_capacity(self, telemetry_df: pd.DataFrame):
        """Buffer levels should never exceed capacity."""
        # Find buffer level/cap column pairs
        level_cols = [c for c in telemetry_df.columns if c.endswith("_level")]

        for level_col in level_cols:
            cap_col = level_col.replace("_level", "_cap")
            if cap_col in telemetry_df.columns:
                levels = telemetry_df[level_col]
                caps = telemetry_df[cap_col]
                # Check each row
                violations = (levels > caps).sum()
                assert violations == 0, (
                    f"Buffer {level_col} exceeded capacity {violations} times"
                )


class TestOEEBenchmarks:
    """Tests that OEE components fall within industry benchmarks."""

    def test_availability_realistic(self, events_df: pd.DataFrame, short_run_hours: float):
        """Machine availability should be within realistic bounds (70-99%)."""
        total_duration_sec = short_run_hours * 3600

        for machine in events_df["machine"].unique():
            machine_events = events_df[events_df["machine"] == machine].copy()

            # Calculate duration of each state
            machine_events["next_time"] = machine_events["timestamp"].shift(-1)
            machine_events["duration"] = (
                machine_events["next_time"] - machine_events["timestamp"]
            )

            down_time = machine_events[machine_events["state"] == "DOWN"]["duration"].sum()
            if pd.isna(down_time):
                down_time = 0

            availability = (total_duration_sec - down_time) / total_duration_sec * 100

            assert 70 <= availability <= 100, (
                f"{machine} availability {availability:.1f}% outside bounds [70-100%]"
            )

    def test_quality_rate_realistic(self, telemetry_df: pd.DataFrame):
        """Quality rate (good/total) should be realistic (>= 90%)."""
        total_good = telemetry_df["good_pallets"].sum()
        total_pallets = telemetry_df["pallets_produced"].sum()

        if total_pallets > 0:
            quality_rate = total_good / total_pallets * 100
            assert quality_rate >= 90, (
                f"Quality rate {quality_rate:.1f}% below minimum 90%"
            )

    def test_oee_within_industry_bounds(
        self, engine: SimulationEngine
    ):
        """Calculated OEE should fall within industry bounds (40-95%)."""
        resolved = engine.loader.resolve_run("baseline_8hr")
        # Use longer duration to ensure meaningful production
        test_duration = 0.5  # 30 minutes
        resolved.run.duration_hours = test_duration

        df_ts, df_ev = engine.run_resolved(resolved)

        total_duration_sec = test_duration * 3600

        # Calculate OEE for Filler (first station, always has events)
        machine = "Filler"
        machine_events = df_ev[df_ev["machine"] == machine].copy()

        assert len(machine_events) > 0, f"No events for {machine}"

        # Calculate state durations
        machine_events["next_time"] = machine_events["timestamp"].shift(-1)
        machine_events["duration"] = (
            machine_events["next_time"] - machine_events["timestamp"]
        )

        execute_time = machine_events[machine_events["state"] == "EXECUTE"][
            "duration"
        ].sum()
        down_time = machine_events[machine_events["state"] == "DOWN"][
            "duration"
        ].sum()

        if pd.isna(execute_time):
            execute_time = 0
        if pd.isna(down_time):
            down_time = 0

        # Availability = (total - down) / total
        available_time = total_duration_sec - down_time
        availability = available_time / total_duration_sec if total_duration_sec > 0 else 0

        # Performance = execute_time / available_time
        performance = execute_time / available_time if available_time > 0 else 0

        # Quality from telemetry (for overall line)
        total_good = df_ts["good_pallets"].sum()
        total_pallets = df_ts["pallets_produced"].sum()
        quality = total_good / total_pallets if total_pallets > 0 else 1.0

        # OEE = A × P × Q
        oee = availability * performance * quality * 100

        # With reliability/performance parameters, OEE should be in realistic range
        assert 40 <= oee <= 95, (
            f"OEE {oee:.1f}% outside industry bounds [40-95%]. "
            f"A={availability*100:.1f}%, P={performance*100:.1f}%, Q={quality*100:.1f}%"
        )


class TestEconomics:
    """Tests for economic calculation validity."""

    def test_gross_margin_positive(self, telemetry_df: pd.DataFrame):
        """Gross margin should be positive when producing good product."""
        total_revenue = telemetry_df["revenue"].sum()
        total_material = telemetry_df["material_cost"].sum()
        total_conversion = telemetry_df["conversion_cost"].sum()
        total_margin = telemetry_df["gross_margin"].sum()

        # Verify margin calculation
        expected_margin = total_revenue - total_material - total_conversion
        assert abs(total_margin - expected_margin) < 1.0, (
            f"Margin calculation mismatch: {total_margin} vs {expected_margin}"
        )

        # With baseline config (selling $450, material $150), margin should be positive
        if total_revenue > 0:
            assert total_margin > 0, (
                f"Gross margin ${total_margin:.2f} should be positive"
            )

    def test_revenue_scales_with_production(
        self, engine: SimulationEngine
    ):
        """More production time should yield more revenue."""
        # Use longer durations for meaningful comparison
        resolved_short = engine.loader.resolve_run("baseline_8hr")
        resolved_short.run.duration_hours = 0.25  # 15 minutes
        resolved_short.run.random_seed = 42

        resolved_long = engine.loader.resolve_run("baseline_8hr")
        resolved_long.run.duration_hours = 0.5  # 30 minutes
        resolved_long.run.random_seed = 42

        df_short, _ = engine.run_resolved(resolved_short)
        df_long, _ = engine.run_resolved(resolved_long)

        revenue_short = df_short["revenue"].sum()
        revenue_long = df_long["revenue"].sum()

        # Longer run should produce more revenue (double time should yield roughly double)
        assert revenue_long >= revenue_short, (
            f"Longer run (${revenue_long:.2f}) should have at least as much revenue "
            f"as shorter (${revenue_short:.2f})"
        )

    def test_conversion_cost_positive(self, telemetry_df: pd.DataFrame):
        """Conversion cost should be positive when machines are running."""
        total_conversion = telemetry_df["conversion_cost"].sum()

        # With machines running, there should be conversion costs
        assert total_conversion > 0, (
            f"Conversion cost ${total_conversion:.2f} should be positive"
        )


class TestTimeSeriesProperties:
    """Tests for time-series data properties."""

    def test_time_increases_monotonically(self, telemetry_df: pd.DataFrame):
        """Time column should increase monotonically."""
        time_diffs = telemetry_df["time"].diff().dropna()
        assert (time_diffs >= 0).all(), "Time should never decrease"

    def test_telemetry_row_count_matches_intervals(
        self, engine: SimulationEngine, short_run_hours: float
    ):
        """Number of telemetry rows should match duration / interval."""
        resolved = engine.loader.resolve_run("baseline_8hr")
        resolved.run.duration_hours = short_run_hours
        interval_sec = resolved.run.telemetry_interval_sec

        df_ts, _ = engine.run_resolved(resolved)

        expected_rows = int(short_run_hours * 3600 / interval_sec)
        actual_rows = len(df_ts)

        # Allow some tolerance (±1 row) due to timing
        assert abs(actual_rows - expected_rows) <= 1, (
            f"Expected ~{expected_rows} rows, got {actual_rows}"
        )
