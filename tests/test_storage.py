"""Tests for DuckDB storage module."""

from pathlib import Path
from typing import Tuple

import duckdb
import pandas as pd
import pytest

from virtual_twin import ConfigLoader, SimulationEngine
from virtual_twin.storage import connect, get_db_path, save_results
from virtual_twin.storage.schema import SCHEMA_DDL, create_tables
from virtual_twin.storage.writer import DuckDBWriter


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create a temporary database file path (does not create the file)."""
    return tmp_path / "test_simpy_results.duckdb"


@pytest.fixture
def config_dir() -> Path:
    """Path to production config directory."""
    return Path(__file__).parent.parent / "config"


@pytest.fixture
def loader(config_dir: Path) -> ConfigLoader:
    """ConfigLoader instance."""
    return ConfigLoader(config_dir)


@pytest.fixture
def resolved(loader: ConfigLoader):
    """Resolved config for testing."""
    resolved = loader.resolve_run("baseline_8hr")
    resolved.run.duration_hours = 0.1  # Short run for testing
    return resolved


@pytest.fixture
def simulation_results(config_dir: Path, resolved) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Run a short simulation and return (telemetry_df, events_df).

    Uses debug_events=True for backward compatibility with OEE storage tests.
    """
    engine = SimulationEngine(str(config_dir), save_to_db=False)
    df_ts, df_ev, _, _ = engine.run_resolved(resolved, debug_events=True)
    return df_ts, df_ev


class TestSchemaCreation:
    """Tests for schema DDL and table creation."""

    def test_schema_ddl_is_valid_sql(self, temp_db: Path):
        """Schema DDL should be valid DuckDB SQL."""
        conn = duckdb.connect(str(temp_db))
        # Should not raise an exception
        conn.execute(SCHEMA_DDL)
        conn.close()

    def test_create_tables_creates_all_tables(self, temp_db: Path):
        """create_tables() should create all 9 tables."""
        conn = duckdb.connect(str(temp_db))
        create_tables(conn)

        # Check tables exist
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        table_names = {t[0] for t in tables}

        expected_tables = {
            "simulation_runs",
            "telemetry",
            "machine_telemetry",
            "events",
            "state_summary",
            "events_detail",
            "run_summary",
            "machine_oee",
            "run_equipment",
        }
        assert expected_tables.issubset(table_names)
        conn.close()

    def test_create_tables_is_idempotent(self, temp_db: Path):
        """create_tables() should be safe to call multiple times."""
        conn = duckdb.connect(str(temp_db))
        create_tables(conn)
        create_tables(conn)  # Should not raise
        conn.close()


class TestDuckDBWriter:
    """Tests for DuckDBWriter class."""

    def test_writer_creates_schema(self, temp_db: Path):
        """Writer should create schema on initialization."""
        writer = DuckDBWriter(temp_db)

        # Check tables exist
        tables = writer.conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        table_names = {t[0] for t in tables}

        assert "simulation_runs" in table_names
        assert "telemetry" in table_names
        writer.close()

    def test_store_run_returns_run_id(
        self,
        temp_db: Path,
        resolved,
        simulation_results: Tuple[pd.DataFrame, pd.DataFrame],
    ):
        """store_run() should return a valid run_id."""
        df_ts, df_ev = simulation_results
        writer = DuckDBWriter(temp_db)

        run_id = writer.store_run(resolved, df_ts, df_ev)

        assert isinstance(run_id, int)
        assert run_id >= 1
        writer.close()

    def test_store_run_inserts_simulation_run(
        self,
        temp_db: Path,
        resolved,
        simulation_results: Tuple[pd.DataFrame, pd.DataFrame],
    ):
        """store_run() should insert a simulation_runs record."""
        df_ts, df_ev = simulation_results
        writer = DuckDBWriter(temp_db)

        run_id = writer.store_run(resolved, df_ts, df_ev)

        # Verify record exists
        result = writer.conn.execute(
            "SELECT run_name, scenario_name, duration_hours FROM simulation_runs WHERE run_id = ?",
            [run_id],
        ).fetchone()

        assert result is not None
        assert result[0] == resolved.run.name
        assert result[1] == resolved.scenario.name
        assert result[2] == resolved.run.duration_hours
        writer.close()

    def test_store_run_inserts_telemetry(
        self,
        temp_db: Path,
        resolved,
        simulation_results: Tuple[pd.DataFrame, pd.DataFrame],
    ):
        """store_run() should insert telemetry records."""
        df_ts, df_ev = simulation_results
        writer = DuckDBWriter(temp_db)

        run_id = writer.store_run(resolved, df_ts, df_ev)

        # Verify telemetry records
        count = writer.conn.execute(
            "SELECT COUNT(*) FROM telemetry WHERE run_id = ?", [run_id]
        ).fetchone()[0]

        assert count == len(df_ts)
        writer.close()

    def test_store_run_inserts_events_when_debug(
        self,
        temp_db: Path,
        resolved,
        simulation_results: Tuple[pd.DataFrame, pd.DataFrame],
    ):
        """store_run() should insert event records when debug_events=True."""
        df_ts, df_ev = simulation_results
        writer = DuckDBWriter(temp_db)

        run_id = writer.store_run(resolved, df_ts, df_ev, debug_events=True)

        # Verify events records
        count = writer.conn.execute(
            "SELECT COUNT(*) FROM events WHERE run_id = ?", [run_id]
        ).fetchone()[0]

        assert count == len(df_ev)
        writer.close()

    def test_store_run_skips_events_by_default(
        self,
        temp_db: Path,
        resolved,
        simulation_results: Tuple[pd.DataFrame, pd.DataFrame],
    ):
        """store_run() should skip events table by default (hybrid mode)."""
        df_ts, df_ev = simulation_results
        writer = DuckDBWriter(temp_db)

        run_id = writer.store_run(resolved, df_ts, df_ev)

        # Verify no events records by default
        count = writer.conn.execute(
            "SELECT COUNT(*) FROM events WHERE run_id = ?", [run_id]
        ).fetchone()[0]

        assert count == 0
        writer.close()

    def test_store_run_inserts_summary(
        self,
        temp_db: Path,
        resolved,
        simulation_results: Tuple[pd.DataFrame, pd.DataFrame],
    ):
        """store_run() should insert a run_summary record."""
        df_ts, df_ev = simulation_results
        writer = DuckDBWriter(temp_db)

        run_id = writer.store_run(resolved, df_ts, df_ev)

        # Verify summary record
        result = writer.conn.execute(
            "SELECT total_pallets, throughput_per_hour FROM run_summary WHERE run_id = ?",
            [run_id],
        ).fetchone()

        assert result is not None
        assert result[0] >= 0  # total_pallets
        writer.close()

    def test_store_run_inserts_machine_oee(
        self,
        temp_db: Path,
        resolved,
        simulation_results: Tuple[pd.DataFrame, pd.DataFrame],
    ):
        """store_run() should insert machine_oee records."""
        df_ts, df_ev = simulation_results
        writer = DuckDBWriter(temp_db)

        run_id = writer.store_run(resolved, df_ts, df_ev)

        # Verify OEE records exist for each machine
        count = writer.conn.execute(
            "SELECT COUNT(*) FROM machine_oee WHERE run_id = ?", [run_id]
        ).fetchone()[0]

        # Should have one record per machine
        assert count > 0
        writer.close()

    def test_store_run_inserts_equipment(
        self,
        temp_db: Path,
        resolved,
        simulation_results: Tuple[pd.DataFrame, pd.DataFrame],
    ):
        """store_run() should insert run_equipment records."""
        df_ts, df_ev = simulation_results
        writer = DuckDBWriter(temp_db)

        run_id = writer.store_run(resolved, df_ts, df_ev)

        # Verify equipment records
        count = writer.conn.execute(
            "SELECT COUNT(*) FROM run_equipment WHERE run_id = ?", [run_id]
        ).fetchone()[0]

        assert count == len(resolved.equipment)
        writer.close()

    def test_store_run_inserts_state_summary(
        self,
        temp_db: Path,
        resolved,
        config_dir: Path,
    ):
        """store_run() should insert state_summary records when provided."""
        from virtual_twin import SimulationEngine

        # Run simulation with aggregator (produces df_state_summary)
        engine = SimulationEngine(str(config_dir), save_to_db=False)
        df_ts, df_ev, df_summary, df_detail = engine.run_resolved(resolved)

        writer = DuckDBWriter(temp_db)
        run_id = writer.store_run(resolved, df_ts, df_ev, df_state_summary=df_summary)

        # Verify state_summary records
        count = writer.conn.execute(
            "SELECT COUNT(*) FROM state_summary WHERE run_id = ?", [run_id]
        ).fetchone()[0]

        # Should have records if aggregator produced summary
        if df_summary is not None and not df_summary.empty:
            assert count == len(df_summary)
        writer.close()

    def test_store_run_inserts_events_detail(
        self,
        temp_db: Path,
        resolved,
        config_dir: Path,
    ):
        """store_run() should insert events_detail records when provided."""
        from virtual_twin import SimulationEngine

        # Run simulation with aggregator (produces df_events_detail)
        engine = SimulationEngine(str(config_dir), save_to_db=False)
        df_ts, df_ev, df_summary, df_detail = engine.run_resolved(resolved)

        writer = DuckDBWriter(temp_db)
        run_id = writer.store_run(resolved, df_ts, df_ev, df_events_detail=df_detail)

        # Verify events_detail records
        count = writer.conn.execute(
            "SELECT COUNT(*) FROM events_detail WHERE run_id = ?", [run_id]
        ).fetchone()[0]

        # Should have records if aggregator produced detail events
        if df_detail is not None and not df_detail.empty:
            assert count == len(df_detail)
        writer.close()

    def test_store_run_oee_from_state_summary(
        self,
        temp_db: Path,
        resolved,
        config_dir: Path,
    ):
        """store_run() should calculate OEE from state_summary when provided."""
        from virtual_twin import SimulationEngine

        # Run simulation with aggregator
        engine = SimulationEngine(str(config_dir), save_to_db=False)
        df_ts, df_ev, df_summary, df_detail = engine.run_resolved(resolved)

        writer = DuckDBWriter(temp_db)
        run_id = writer.store_run(resolved, df_ts, df_ev, df_state_summary=df_summary)

        # Verify OEE records exist for each machine
        count = writer.conn.execute(
            "SELECT COUNT(*) FROM machine_oee WHERE run_id = ?", [run_id]
        ).fetchone()[0]

        # Should have one record per machine
        assert count > 0
        writer.close()


class TestPublicAPI:
    """Tests for the public storage API."""

    def test_get_db_path_returns_default(self):
        """get_db_path() should return the default path."""
        path = get_db_path()
        assert path == Path("./virtual_twin_results.duckdb")

    def test_save_results_creates_db(
        self,
        temp_db: Path,
        resolved,
        simulation_results: Tuple[pd.DataFrame, pd.DataFrame],
    ):
        """save_results() should create the database file."""
        df_ts, df_ev = simulation_results

        run_id = save_results(resolved, df_ts, df_ev, temp_db)

        assert temp_db.exists()
        assert isinstance(run_id, int)

    def test_connect_returns_connection(self, temp_db: Path):
        """connect() should return a valid DuckDB connection."""
        # Create empty db with schema
        writer = DuckDBWriter(temp_db)
        writer.close()

        conn = connect(temp_db)
        assert conn is not None

        # Should be able to query
        result = conn.execute("SELECT 1").fetchone()
        assert result[0] == 1
        conn.close()

    def test_views_are_queryable(
        self,
        temp_db: Path,
        resolved,
        simulation_results: Tuple[pd.DataFrame, pd.DataFrame],
    ):
        """Analytics views should be queryable."""
        df_ts, df_ev = simulation_results
        save_results(resolved, df_ts, df_ev, temp_db)

        conn = connect(temp_db)

        # Test v_run_comparison view
        df = conn.execute("SELECT * FROM v_run_comparison").df()
        assert len(df) == 1

        # Test v_machine_oee view
        df = conn.execute("SELECT * FROM v_machine_oee").df()
        assert len(df) > 0

        conn.close()


class TestDataIntegrity:
    """Tests for data integrity and correctness."""

    def test_config_snapshot_is_valid_json(
        self,
        temp_db: Path,
        resolved,
        simulation_results: Tuple[pd.DataFrame, pd.DataFrame],
    ):
        """Config snapshot should be valid JSON."""
        import json

        df_ts, df_ev = simulation_results
        writer = DuckDBWriter(temp_db)
        run_id = writer.store_run(resolved, df_ts, df_ev)

        result = writer.conn.execute(
            "SELECT config_snapshot FROM simulation_runs WHERE run_id = ?",
            [run_id],
        ).fetchone()

        snapshot = result[0]
        # Should be parseable as JSON
        parsed = json.loads(snapshot) if isinstance(snapshot, str) else snapshot
        assert "run" in parsed
        assert "scenario" in parsed
        assert "equipment" in parsed
        writer.close()

    def test_summary_totals_match_telemetry(
        self,
        temp_db: Path,
        resolved,
        simulation_results: Tuple[pd.DataFrame, pd.DataFrame],
    ):
        """Summary totals should match telemetry aggregations."""
        df_ts, df_ev = simulation_results
        writer = DuckDBWriter(temp_db)
        run_id = writer.store_run(resolved, df_ts, df_ev)

        # Get summary values
        summary = writer.conn.execute(
            "SELECT total_pallets, total_revenue FROM run_summary WHERE run_id = ?",
            [run_id],
        ).fetchone()

        # Get telemetry aggregations
        tel_agg = writer.conn.execute(
            "SELECT SUM(pallets_produced), SUM(revenue) FROM telemetry WHERE run_id = ?",
            [run_id],
        ).fetchone()

        assert summary[0] == tel_agg[0]  # total_pallets
        # Revenue might have floating point differences
        if summary[1] and tel_agg[1]:
            assert abs(summary[1] - tel_agg[1]) < 0.01
        writer.close()

    def test_oee_availability_is_bounded(
        self,
        temp_db: Path,
        resolved,
        simulation_results: Tuple[pd.DataFrame, pd.DataFrame],
    ):
        """OEE availability should be between 0 and 100."""
        df_ts, df_ev = simulation_results
        writer = DuckDBWriter(temp_db)
        run_id = writer.store_run(resolved, df_ts, df_ev)

        results = writer.conn.execute(
            "SELECT availability_percent FROM machine_oee WHERE run_id = ?",
            [run_id],
        ).fetchall()

        for (availability,) in results:
            assert 0 <= availability <= 100
        writer.close()
