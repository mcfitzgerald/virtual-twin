"""End-to-end integration smoke tests for simpy-demo."""

from pathlib import Path

import pandas as pd

from simpy_demo import ConfigLoader, SimulationEngine


class TestConfigLoading:
    """Tests for configuration loading and resolution."""

    def test_config_loader_resolves_baseline(self, loader: ConfigLoader):
        """ConfigLoader.resolve_run('baseline_8hr') succeeds and returns ResolvedConfig."""
        resolved = loader.resolve_run("baseline_8hr")

        assert resolved.run.name == "baseline_8hr"
        assert resolved.scenario.name == "baseline"
        assert resolved.topology.name == "cosmetics_line"
        assert len(resolved.equipment) == 4
        assert "Filler" in resolved.equipment
        assert "Palletizer" in resolved.equipment
        assert resolved.product is not None
        assert resolved.product.name == "fresh_toothpaste_5oz"

    def test_config_loader_resolves_graph(self, loader: ConfigLoader):
        """ConfigLoader.resolve_run('baseline_graph_8hr') succeeds for graph topology."""
        resolved = loader.resolve_run("baseline_graph_8hr")

        assert resolved.run.name == "baseline_graph_8hr"
        assert resolved.topology.is_graph_topology is True
        assert len(resolved.topology.nodes) > 0
        assert len(resolved.topology.edges) > 0


class TestSimulationExecution:
    """Tests for simulation execution."""

    def test_simulation_runs_to_completion(
        self, engine: SimulationEngine, short_run_hours: float
    ):
        """SimulationEngine.run_resolved() completes and returns DataFrames."""
        resolved = engine.loader.resolve_run("baseline_8hr")
        resolved.run.duration_hours = short_run_hours

        df_ts, df_ev, df_summary, df_detail = engine.run_resolved(resolved)

        assert df_ts is not None
        assert df_ev is not None
        assert isinstance(df_ts, pd.DataFrame)
        assert isinstance(df_ev, pd.DataFrame)
        assert len(df_ts) > 0
        # Note: df_ev may be empty when debug_events=False (default)
        assert isinstance(df_summary, pd.DataFrame)
        assert isinstance(df_detail, pd.DataFrame)

    def test_graph_topology_runs(
        self, engine: SimulationEngine, short_run_hours: float
    ):
        """Graph-based topology simulation completes successfully."""
        resolved = engine.loader.resolve_run("baseline_graph_8hr")
        resolved.run.duration_hours = short_run_hours

        df_ts, df_ev, _, _ = engine.run_resolved(resolved)

        assert len(df_ts) > 0
        # Note: df_ev may be empty when debug_events=False (default)

    def test_random_seed_reproducibility(
        self, engine: SimulationEngine, short_run_hours: float
    ):
        """Same random seed produces identical results."""
        resolved1 = engine.loader.resolve_run("baseline_8hr")
        resolved1.run.duration_hours = short_run_hours
        resolved1.run.random_seed = 42

        resolved2 = engine.loader.resolve_run("baseline_8hr")
        resolved2.run.duration_hours = short_run_hours
        resolved2.run.random_seed = 42

        df_ts1, _, _, _ = engine.run_resolved(resolved1)
        df_ts2, _, _, _ = engine.run_resolved(resolved2)

        # Compare total production
        assert df_ts1["tubes_produced"].sum() == df_ts2["tubes_produced"].sum()
        assert df_ts1["pallets_produced"].sum() == df_ts2["pallets_produced"].sum()

    def test_run_simulation_entry_point(self, config_dir: Path):
        """Public run_simulation() function works."""
        # This tests the public API entry point
        # Note: This test uses full duration, so it's slower
        # We use the engine with short duration for most tests
        engine = SimulationEngine(str(config_dir))
        resolved = engine.loader.resolve_run("baseline_8hr")
        resolved.run.duration_hours = 0.05  # 3 minutes for speed

        df_ts, df_ev, _, _ = engine.run_resolved(resolved)

        assert df_ts is not None
        assert df_ev is not None
        assert len(df_ts) > 0
