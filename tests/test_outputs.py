"""Output schema validation tests for virtual-twin.

These tests verify that simulation outputs have the expected structure
and column names, ensuring downstream consumers can rely on the schema.
"""

import pandas as pd


class TestTelemetrySchema:
    """Tests for telemetry DataFrame schema."""

    def test_telemetry_has_time_columns(self, telemetry_df: pd.DataFrame):
        """Telemetry DataFrame has time and datetime columns."""
        assert "time" in telemetry_df.columns, "Missing 'time' column"
        assert "datetime" in telemetry_df.columns, "Missing 'datetime' column"

    def test_telemetry_has_production_columns(self, telemetry_df: pd.DataFrame):
        """Telemetry DataFrame has production count columns."""
        expected_cols = [
            "tubes_produced",
            "cases_produced",
            "pallets_produced",
            "good_pallets",
            "defective_pallets",
        ]
        for col in expected_cols:
            assert col in telemetry_df.columns, f"Missing production column: {col}"

    def test_telemetry_has_quality_columns(self, telemetry_df: pd.DataFrame):
        """Telemetry DataFrame has quality tracking columns."""
        expected_cols = ["defects_created", "defects_detected"]
        for col in expected_cols:
            assert col in telemetry_df.columns, f"Missing quality column: {col}"

    def test_telemetry_has_economic_columns(self, telemetry_df: pd.DataFrame):
        """Telemetry DataFrame has economic columns when product is defined."""
        expected_cols = [
            "sku_name",
            "revenue",
            "material_cost",
            "conversion_cost",
            "gross_margin",
        ]
        for col in expected_cols:
            assert col in telemetry_df.columns, f"Missing economic column: {col}"

    def test_telemetry_has_buffer_columns(self, telemetry_df: pd.DataFrame):
        """Telemetry DataFrame has buffer level columns for each machine."""
        # Buffer columns follow pattern: Buf_<machine>_level and Buf_<machine>_cap
        buffer_level_cols = [c for c in telemetry_df.columns if c.endswith("_level")]
        buffer_cap_cols = [c for c in telemetry_df.columns if c.endswith("_cap")]

        assert len(buffer_level_cols) > 0, "No buffer level columns found"
        assert len(buffer_cap_cols) > 0, "No buffer capacity columns found"

    def test_telemetry_has_state_columns(self, telemetry_df: pd.DataFrame):
        """Telemetry DataFrame has state columns for each machine."""
        # State columns follow pattern: <machine>_state and <machine>_output
        state_cols = [c for c in telemetry_df.columns if c.endswith("_state")]
        output_cols = [c for c in telemetry_df.columns if c.endswith("_output")]

        assert len(state_cols) > 0, "No machine state columns found"
        assert len(output_cols) > 0, "No machine output columns found"

        # Check for expected machines
        expected_machines = ["Filler", "Inspector", "Packer", "Palletizer"]
        for machine in expected_machines:
            assert f"{machine}_state" in telemetry_df.columns, f"Missing {machine}_state"


class TestEventsSchema:
    """Tests for events DataFrame schema."""

    def test_events_has_required_columns(self, events_df: pd.DataFrame):
        """Events DataFrame has required columns."""
        expected_cols = ["timestamp", "machine", "state", "event_type"]
        for col in expected_cols:
            assert col in events_df.columns, f"Missing events column: {col}"

    def test_events_has_datetime(self, events_df: pd.DataFrame):
        """Events DataFrame has datetime column."""
        assert "datetime" in events_df.columns, "Missing 'datetime' column in events"
