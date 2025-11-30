"""Unit tests for EventAggregator class."""

from datetime import datetime, timedelta

import pandas as pd

from virtual_twin.aggregation import (
    CONTEXT_WINDOW,
    INTERESTING_STATES,
    BucketStats,
    EventAggregator,
)


class TestBucketStats:
    """Tests for BucketStats dataclass."""

    def test_add_duration_execute(self):
        bucket = BucketStats(
            bucket_index=0,
            bucket_start_ts=datetime.now(),
            machine_name="Filler",
        )
        bucket.add_duration("EXECUTE", 10.0)
        assert bucket.execute_sec == 10.0

    def test_add_duration_all_states(self):
        bucket = BucketStats(
            bucket_index=0,
            bucket_start_ts=datetime.now(),
            machine_name="Filler",
        )
        bucket.add_duration("EXECUTE", 100.0)
        bucket.add_duration("STARVED", 50.0)
        bucket.add_duration("BLOCKED", 30.0)
        bucket.add_duration("DOWN", 15.0)
        bucket.add_duration("JAMMED", 5.0)

        assert bucket.execute_sec == 100.0
        assert bucket.starved_sec == 50.0
        assert bucket.blocked_sec == 30.0
        assert bucket.down_sec == 15.0
        assert bucket.jammed_sec == 5.0
        assert bucket.total_sec == 200.0

    def test_add_duration_case_insensitive(self):
        bucket = BucketStats(
            bucket_index=0,
            bucket_start_ts=datetime.now(),
            machine_name="Filler",
        )
        bucket.add_duration("execute", 10.0)
        bucket.add_duration("Execute", 10.0)
        bucket.add_duration("EXECUTE", 10.0)
        assert bucket.execute_sec == 30.0

    def test_availability_pct_normal(self):
        bucket = BucketStats(
            bucket_index=0,
            bucket_start_ts=datetime.now(),
            machine_name="Filler",
        )
        bucket.execute_sec = 80.0
        bucket.down_sec = 15.0
        bucket.jammed_sec = 5.0
        # Availability = 80 / (80 + 15 + 5) = 80%
        assert bucket.availability_pct == 80.0

    def test_availability_pct_no_losses(self):
        bucket = BucketStats(
            bucket_index=0,
            bucket_start_ts=datetime.now(),
            machine_name="Filler",
        )
        bucket.execute_sec = 100.0
        assert bucket.availability_pct == 100.0

    def test_availability_pct_zero_time(self):
        bucket = BucketStats(
            bucket_index=0,
            bucket_start_ts=datetime.now(),
            machine_name="Filler",
        )
        assert bucket.availability_pct is None


class TestEventAggregator:
    """Tests for EventAggregator class."""

    def test_init_defaults(self):
        agg = EventAggregator()
        assert agg.bucket_size_sec == 300.0
        assert len(agg._buckets) == 0
        assert len(agg._event_buffer) == 0
        assert len(agg._interesting_indices) == 0

    def test_get_bucket_index(self):
        agg = EventAggregator(bucket_size_sec=300.0)
        assert agg._get_bucket_index(0.0) == 0
        assert agg._get_bucket_index(299.9) == 0
        assert agg._get_bucket_index(300.0) == 1
        assert agg._get_bucket_index(600.0) == 2

    def test_on_state_change_creates_bucket(self):
        agg = EventAggregator(bucket_size_sec=300.0)
        agg.on_state_change(
            machine_name="Filler",
            new_state="EXECUTE",
            sim_time_sec=100.0,
            prev_state="STARVED",
            duration_sec=50.0,
        )

        assert (0, "Filler") in agg._buckets
        bucket = agg._buckets[(0, "Filler")]
        assert bucket.starved_sec == 50.0
        assert bucket.transition_count == 1

    def test_on_state_change_accumulates_duration(self):
        agg = EventAggregator(bucket_size_sec=300.0)

        # First transition
        agg.on_state_change(
            machine_name="Filler",
            new_state="EXECUTE",
            sim_time_sec=50.0,
            prev_state="STARVED",
            duration_sec=50.0,
        )

        # Second transition
        agg.on_state_change(
            machine_name="Filler",
            new_state="STARVED",
            sim_time_sec=100.0,
            prev_state="EXECUTE",
            duration_sec=50.0,
        )

        bucket = agg._buckets[(0, "Filler")]
        assert bucket.starved_sec == 50.0
        assert bucket.execute_sec == 50.0
        assert bucket.transition_count == 2

    def test_on_state_change_interesting_states(self):
        agg = EventAggregator()

        agg.on_state_change(
            machine_name="Filler",
            new_state="DOWN",
            sim_time_sec=100.0,
            prev_state="EXECUTE",
            duration_sec=10.0,
        )
        assert 0 in agg._interesting_indices

        agg.on_state_change(
            machine_name="Filler",
            new_state="JAMMED",
            sim_time_sec=200.0,
            prev_state="DOWN",
            duration_sec=50.0,
        )
        assert 1 in agg._interesting_indices

    def test_on_state_change_tracks_down_count(self):
        agg = EventAggregator()

        agg.on_state_change(
            machine_name="Filler",
            new_state="DOWN",
            sim_time_sec=100.0,
        )
        agg.on_state_change(
            machine_name="Filler",
            new_state="EXECUTE",
            sim_time_sec=200.0,
        )
        agg.on_state_change(
            machine_name="Filler",
            new_state="DOWN",
            sim_time_sec=250.0,
        )

        bucket = agg._buckets[(0, "Filler")]
        assert bucket.down_count == 2

    def test_on_state_change_tracks_jammed_count(self):
        agg = EventAggregator()

        agg.on_state_change(
            machine_name="Filler",
            new_state="JAMMED",
            sim_time_sec=100.0,
        )

        bucket = agg._buckets[(0, "Filler")]
        assert bucket.jammed_count == 1

    def test_duration_spans_buckets(self):
        agg = EventAggregator(bucket_size_sec=100.0)

        # Event at 150, with duration 100 that spans from 50-150
        # This spans bucket 0 (50-100) and bucket 1 (100-150)
        agg.on_state_change(
            machine_name="Filler",
            new_state="DOWN",
            sim_time_sec=150.0,
            prev_state="EXECUTE",
            duration_sec=100.0,
        )

        bucket0 = agg._buckets[(0, "Filler")]
        bucket1 = agg._buckets[(1, "Filler")]

        # Bucket 0 should have 50 seconds (50-100)
        assert bucket0.execute_sec == 50.0
        # Bucket 1 should have 50 seconds (100-150)
        assert bucket1.execute_sec == 50.0

    def test_multiple_machines(self):
        agg = EventAggregator()

        agg.on_state_change(
            machine_name="Filler",
            new_state="EXECUTE",
            sim_time_sec=100.0,
            prev_state="STARVED",
            duration_sec=100.0,
        )
        agg.on_state_change(
            machine_name="Packer",
            new_state="EXECUTE",
            sim_time_sec=100.0,
            prev_state="BLOCKED",
            duration_sec=100.0,
        )

        assert (0, "Filler") in agg._buckets
        assert (0, "Packer") in agg._buckets
        assert agg._buckets[(0, "Filler")].starved_sec == 100.0
        assert agg._buckets[(0, "Packer")].blocked_sec == 100.0

    def test_finalize_accumulates_final_state(self):
        agg = EventAggregator(bucket_size_sec=300.0)

        # Enter EXECUTE at time 100
        agg.on_state_change(
            machine_name="Filler",
            new_state="EXECUTE",
            sim_time_sec=100.0,
            prev_state="STARVED",
            duration_sec=100.0,
        )

        # Finalize at time 500 (400 seconds in EXECUTE state)
        agg.finalize(total_time_sec=500.0)

        bucket0 = agg._buckets[(0, "Filler")]
        bucket1 = agg._buckets[(1, "Filler")]

        # Bucket 0: 100 starved + 200 execute (100-300)
        assert bucket0.starved_sec == 100.0
        assert bucket0.execute_sec == 200.0

        # Bucket 1: 200 execute (300-500)
        assert bucket1.execute_sec == 200.0

    def test_get_summary_df_empty(self):
        agg = EventAggregator()
        df = agg.get_summary_df()

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert "bucket_start_ts" in df.columns
        assert "availability_pct" in df.columns

    def test_get_summary_df_structure(self):
        agg = EventAggregator()

        agg.on_state_change(
            machine_name="Filler",
            new_state="EXECUTE",
            sim_time_sec=100.0,
            prev_state="STARVED",
            duration_sec=50.0,
        )

        df = agg.get_summary_df()

        expected_columns = [
            "bucket_start_ts",
            "bucket_index",
            "machine_name",
            "execute_sec",
            "starved_sec",
            "blocked_sec",
            "down_sec",
            "jammed_sec",
            "transition_count",
            "down_count",
            "jammed_count",
            "availability_pct",
        ]
        assert list(df.columns) == expected_columns
        assert len(df) == 1
        assert df.iloc[0]["machine_name"] == "Filler"
        assert df.iloc[0]["starved_sec"] == 50.0

    def test_get_summary_df_sorted(self):
        agg = EventAggregator(bucket_size_sec=100.0)

        # Add events in non-sorted order
        agg.on_state_change("Packer", "EXECUTE", 150.0)
        agg.on_state_change("Filler", "EXECUTE", 50.0)
        agg.on_state_change("Filler", "EXECUTE", 150.0)

        df = agg.get_summary_df()

        # Should be sorted by machine_name, then bucket_index
        assert df.iloc[0]["machine_name"] == "Filler"
        assert df.iloc[0]["bucket_index"] == 0
        assert df.iloc[1]["machine_name"] == "Filler"
        assert df.iloc[1]["bucket_index"] == 1
        assert df.iloc[2]["machine_name"] == "Packer"

    def test_get_detail_df_empty_no_interesting(self):
        agg = EventAggregator()

        # Add non-interesting events
        agg.on_state_change("Filler", "EXECUTE", 100.0)
        agg.on_state_change("Filler", "STARVED", 200.0)

        df = agg.get_detail_df()
        assert len(df) == 0

    def test_get_detail_df_includes_interesting(self):
        agg = EventAggregator()

        agg.on_state_change("Filler", "EXECUTE", 100.0)
        agg.on_state_change("Filler", "DOWN", 200.0)  # Interesting!
        agg.on_state_change("Filler", "EXECUTE", 300.0)

        df = agg.get_detail_df()

        # Should include DOWN event and context (EXECUTE before and after)
        assert len(df) == 3

        # Check is_interesting flag
        interesting_rows = df[df["is_interesting"]]
        assert len(interesting_rows) == 1
        assert interesting_rows.iloc[0]["state"] == "DOWN"

    def test_get_detail_df_context_window(self):
        agg = EventAggregator()

        # Add many events
        for i in range(20):
            agg.on_state_change("Filler", "EXECUTE", float(i * 10))

        # Add interesting event
        agg.on_state_change("Filler", "DOWN", 200.0)

        # Add more events
        for i in range(20):
            agg.on_state_change("Filler", "STARVED", 210.0 + float(i * 10))

        df = agg.get_detail_df()

        # Should include DOWN + CONTEXT_WINDOW before + CONTEXT_WINDOW after
        # Total = 1 + 5 + 5 = 11 events
        assert len(df) == 11

    def test_get_detail_df_structure(self):
        agg = EventAggregator()

        agg.on_state_change(
            machine_name="Filler",
            new_state="DOWN",
            sim_time_sec=100.0,
            prev_state="EXECUTE",
            duration_sec=50.0,
        )

        df = agg.get_detail_df()

        expected_columns = [
            "ts",
            "sim_time_sec",
            "machine_name",
            "state",
            "prev_state",
            "duration_sec",
            "is_interesting",
        ]
        assert list(df.columns) == expected_columns

    def test_constants(self):
        """Verify module constants are set correctly."""
        assert "DOWN" in INTERESTING_STATES
        assert "JAMMED" in INTERESTING_STATES
        assert CONTEXT_WINDOW == 5


class TestEventAggregatorIntegration:
    """Integration-style tests for EventAggregator."""

    def test_simulated_production_run(self):
        """Simulate a realistic production scenario."""
        start_ts = datetime(2024, 1, 1, 8, 0, 0)
        agg = EventAggregator(bucket_size_sec=300.0, sim_start_ts=start_ts)

        # Simulate 10 minutes of production with some failures
        events = [
            ("STARVED", 0.0, None, None),
            ("EXECUTE", 10.0, "STARVED", 10.0),
            ("STARVED", 15.0, "EXECUTE", 5.0),
            ("EXECUTE", 20.0, "STARVED", 5.0),
            ("DOWN", 100.0, "EXECUTE", 80.0),  # Breakdown!
            ("EXECUTE", 160.0, "DOWN", 60.0),  # Repair complete
            ("JAMMED", 200.0, "EXECUTE", 40.0),  # Microstop!
            ("EXECUTE", 210.0, "JAMMED", 10.0),  # Cleared
            ("STARVED", 400.0, "EXECUTE", 190.0),
            ("EXECUTE", 420.0, "STARVED", 20.0),
            ("BLOCKED", 500.0, "EXECUTE", 80.0),
            ("EXECUTE", 550.0, "BLOCKED", 50.0),
        ]

        for state, time, prev, dur in events:
            agg.on_state_change("Filler", state, time, prev, dur)

        agg.finalize(600.0)

        summary_df = agg.get_summary_df()
        detail_df = agg.get_detail_df()

        # Check summary
        assert len(summary_df) == 2  # 2 buckets (0-300, 300-600)

        bucket0 = summary_df[summary_df["bucket_index"] == 0].iloc[0]
        bucket1 = summary_df[summary_df["bucket_index"] == 1].iloc[0]

        # Bucket 0: starved=15, execute=135, down=60, jammed=10 = 220 + some more
        assert bucket0["down_sec"] == 60.0
        assert bucket0["jammed_sec"] == 10.0
        assert bucket0["down_count"] == 1
        assert bucket0["jammed_count"] == 1

        # Bucket 1: should have no DOWN or JAMMED events
        assert bucket1["down_count"] == 0
        assert bucket1["jammed_count"] == 0

        # Detail should have 2 interesting events (DOWN and JAMMED)
        interesting = detail_df[detail_df["is_interesting"]]
        assert len(interesting) == 2
        assert set(interesting["state"]) == {"DOWN", "JAMMED"}

    def test_bucket_timestamps_aligned(self):
        """Verify bucket timestamps are properly aligned."""
        start_ts = datetime(2024, 1, 1, 8, 0, 0)
        agg = EventAggregator(bucket_size_sec=300.0, sim_start_ts=start_ts)

        agg.on_state_change("Filler", "EXECUTE", 0.0)
        agg.on_state_change("Filler", "EXECUTE", 350.0)
        agg.on_state_change("Filler", "EXECUTE", 650.0)

        df = agg.get_summary_df()

        expected_starts = [
            start_ts,
            start_ts + timedelta(seconds=300),
            start_ts + timedelta(seconds=600),
        ]

        for i, expected_ts in enumerate(expected_starts):
            assert df.iloc[i]["bucket_start_ts"] == expected_ts
