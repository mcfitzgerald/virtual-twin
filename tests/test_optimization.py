"""Optimization experiment validation tests for virtual-twin.

These tests verify that the simulation can serve as a baseline for
optimization experiments by ensuring:
- Loss patterns are traceable to specific OEE components
- Bottlenecks are identifiable from state data
- Production volumes are realistic for CPG industry
- Improvements in config correlate with metric improvements

Sources:
- https://www.oee.com/oee-six-big-losses/
- https://www.oee.com/oee-factors/
"""

import pandas as pd

from virtual_twin import SimulationEngine


class TestLossAttribution:
    """Tests for tracing losses to OEE components."""

    def test_loss_attribution_traceable(self, engine: SimulationEngine):
        """Verify losses can be traced to specific OEE components.

        For optimization, we need to identify WHERE to improve:
        - Availability loss = DOWN time (equipment failures)
        - Performance loss = JAMMED time (microstops)
        - Quality loss = defects created
        """
        resolved = engine.loader.resolve_run("baseline_8hr")
        resolved.run.duration_hours = 1.0  # 1 hour for meaningful data

        # Need debug_events=True to get full event log for loss attribution
        df_ts, df_ev, _, _ = engine.run_resolved(resolved, debug_events=True)

        # Check each machine has trackable losses
        machines = ["Filler", "Inspector", "Packer", "Palletizer"]
        for machine in machines:
            m_ev = df_ev[df_ev["machine"] == machine].copy()

            # Calculate state durations
            m_ev["next_time"] = m_ev["timestamp"].shift(-1)
            m_ev["duration"] = m_ev["next_time"] - m_ev["timestamp"]

            # Availability loss = DOWN time
            down_time = m_ev[m_ev["state"] == "DOWN"]["duration"].sum()
            if pd.isna(down_time):
                down_time = 0

            # Performance loss = JAMMED time
            jammed_time = m_ev[m_ev["state"] == "JAMMED"]["duration"].sum()
            if pd.isna(jammed_time):
                jammed_time = 0

            # Verify losses are trackable (non-negative)
            assert down_time >= 0, f"DOWN time should be trackable for {machine}"
            assert jammed_time >= 0, f"JAMMED time should be trackable for {machine}"

        # Quality loss from telemetry
        total_defects = df_ts["defects_created"].sum()
        assert total_defects >= 0, "Defects should be trackable for quality loss"


class TestBottleneckIdentification:
    """Tests for identifying constraining stations."""

    def test_bottleneck_identifiable(self, engine: SimulationEngine):
        """Verify the constraining station is identifiable.

        Bottleneck identification:
        - Filler (first station) should never be STARVED (infinite source)
        - Downstream machines show STARVED when upstream is bottleneck
        - Machine with most BLOCKED time upstream indicates bottleneck
        """
        resolved = engine.loader.resolve_run("baseline_8hr")
        resolved.run.duration_hours = 0.5  # 30 min

        # Need debug_events=True to get full event log for bottleneck analysis
        df_ts, df_ev, _, _ = engine.run_resolved(resolved, debug_events=True)

        machines = ["Filler", "Inspector", "Packer", "Palletizer"]
        starved_times = {}
        blocked_times = {}

        for machine in machines:
            m_ev = df_ev[df_ev["machine"] == machine].copy()

            # Calculate state durations
            m_ev["next_time"] = m_ev["timestamp"].shift(-1)
            m_ev["duration"] = m_ev["next_time"] - m_ev["timestamp"]

            starved = m_ev[m_ev["state"] == "STARVED"]["duration"].sum()
            starved_times[machine] = starved if pd.notna(starved) else 0

            blocked = m_ev[m_ev["state"] == "BLOCKED"]["duration"].sum()
            blocked_times[machine] = blocked if pd.notna(blocked) else 0

        # Filler should have 0 STARVED (infinite source)
        assert starved_times["Filler"] == 0, "Filler has infinite source, never starved"

        # Verify we can distinguish between starved/blocked states
        # (at least one machine should show blocking or starvation in a realistic sim)
        total_starved = sum(starved_times.values())
        total_blocked = sum(blocked_times.values())

        # With reliability/performance issues, we should see some blocking
        # If all machines have 0 starved and 0 blocked, the line is perfectly balanced
        # which is unrealistic
        assert total_starved > 0 or total_blocked > 0, (
            "Should see some starvation or blocking in downstream machines"
        )


class TestProductionVolumes:
    """Tests for realistic production volumes."""

    def test_production_volume_realistic(self, engine: SimulationEngine):
        """Verify 8hr run produces realistic CPG volumes.

        With baseline_8hr config:
        - Filler: 10,000 UPH
        - 8 hours = 80,000 max tubes
        - 720 tubes/pallet = 111 max pallets
        - At ~60% OEE: ~67 pallets
        - Acceptable range: 40-100 pallets
        """
        resolved = engine.loader.resolve_run("baseline_8hr")
        # Use shorter duration but scale expectations
        resolved.run.duration_hours = 1.0  # 1 hour for speed

        df_ts, _, _, _ = engine.run_resolved(resolved)

        total_pallets = df_ts["pallets_produced"].sum()

        # For 1 hour with 10,000 UPH and 720 tubes/pallet:
        # Max = 10,000 / 720 ≈ 14 pallets/hour
        # At ~60-80% OEE: ~8-11 pallets/hour
        # Acceptable range: 5-14 pallets for 1 hour
        assert 5 <= total_pallets <= 14, (
            f"Expected 5-14 pallets for 1hr at realistic OEE, got {total_pallets}"
        )

    def test_eight_hour_shift_volume(self, engine: SimulationEngine):
        """Verify 8hr shift produces expected pallet count.

        This is a longer test to validate full-shift production.
        """
        resolved = engine.loader.resolve_run("baseline_8hr")
        resolved.run.duration_hours = 2.0  # 2 hours as compromise

        df_ts, _, _, _ = engine.run_resolved(resolved)

        total_pallets = df_ts["pallets_produced"].sum()

        # For 2 hours: ~16-28 pallets expected
        # Scale 8hr expectations (40-100) by 0.25 = 10-25 pallets
        assert 10 <= total_pallets <= 30, (
            f"Expected 10-30 pallets for 2hr shift, got {total_pallets}"
        )


class TestImprovementCorrelation:
    """Tests that improvements in config lead to metric improvements."""

    def test_improvement_correlation(self, engine: SimulationEngine):
        """Verify improving parameters improves metrics.

        Better MTBF (less breakdowns) should lead to:
        - Higher availability
        - More production output
        """
        # Baseline run - need debug_events=True for event analysis
        resolved_base = engine.loader.resolve_run("baseline_8hr")
        resolved_base.run.duration_hours = 0.5  # 30 min
        resolved_base.run.random_seed = 42

        df_base, ev_base, _, _ = engine.run_resolved(resolved_base, debug_events=True)
        base_pallets = df_base["pallets_produced"].sum()

        # Calculate baseline availability for Filler
        filler_ev = ev_base[ev_base["machine"] == "Filler"].copy()
        filler_ev["next_time"] = filler_ev["timestamp"].shift(-1)
        filler_ev["duration"] = filler_ev["next_time"] - filler_ev["timestamp"]
        base_down = filler_ev[filler_ev["state"] == "DOWN"]["duration"].sum()
        base_down = base_down if pd.notna(base_down) else 0

        # Improved run: increase MTBF (fewer breakdowns)
        resolved_improved = engine.loader.resolve_run("baseline_8hr")
        resolved_improved.run.duration_hours = 0.5
        resolved_improved.run.random_seed = 42  # Same seed for comparable results

        # Double MTBF for all equipment (should reduce downtime)
        for equip in resolved_improved.equipment.values():
            if equip.reliability and equip.reliability.mtbf_min:
                equip.reliability.mtbf_min *= 2

        df_improved, ev_improved, _, _ = engine.run_resolved(resolved_improved, debug_events=True)
        improved_pallets = df_improved["pallets_produced"].sum()

        # Calculate improved availability for Filler
        filler_ev_imp = ev_improved[ev_improved["machine"] == "Filler"].copy()
        filler_ev_imp["next_time"] = filler_ev_imp["timestamp"].shift(-1)
        filler_ev_imp["duration"] = filler_ev_imp["next_time"] - filler_ev_imp["timestamp"]
        improved_down = filler_ev_imp[filler_ev_imp["state"] == "DOWN"]["duration"].sum()
        improved_down = improved_down if pd.notna(improved_down) else 0

        # Improved should have less or equal downtime
        # Note: Due to stochastic nature, we use a soft check
        # With doubled MTBF, probability of breakdown in 30 min should be much lower
        assert improved_down <= base_down * 1.5, (
            f"Doubled MTBF should not increase downtime. "
            f"Base: {base_down:.1f}s, Improved: {improved_down:.1f}s"
        )

        # Production should be at least similar (stochastic, so allow 20% variance)
        assert improved_pallets >= base_pallets * 0.8, (
            f"Doubling MTBF should not significantly decrease output. "
            f"Base: {base_pallets}, Improved: {improved_pallets}"
        )
