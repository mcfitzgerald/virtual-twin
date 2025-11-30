"""Shared test fixtures for simpy-demo integration tests."""

from pathlib import Path
from typing import Tuple

import pandas as pd
import pytest

from simpy_demo import ConfigLoader, SimulationEngine


@pytest.fixture
def config_dir() -> Path:
    """Path to production config directory."""
    return Path(__file__).parent.parent / "config"


@pytest.fixture
def short_run_hours() -> float:
    """Short duration for fast tests (6 min sim time)."""
    return 0.1


@pytest.fixture
def loader(config_dir: Path) -> ConfigLoader:
    """ConfigLoader instance."""
    return ConfigLoader(config_dir)


@pytest.fixture
def engine(config_dir: Path) -> SimulationEngine:
    """SimulationEngine instance (with DB saving disabled for tests)."""
    return SimulationEngine(str(config_dir), save_to_db=False)


@pytest.fixture
def baseline_resolved(loader: ConfigLoader):
    """Resolved baseline_8hr config."""
    return loader.resolve_run("baseline_8hr")


@pytest.fixture
def short_simulation(engine: SimulationEngine, short_run_hours: float) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Run a short simulation and return (telemetry_df, events_df)."""
    resolved = engine.loader.resolve_run("baseline_8hr")
    resolved.run.duration_hours = short_run_hours
    return engine.run_resolved(resolved)


@pytest.fixture
def telemetry_df(short_simulation: Tuple[pd.DataFrame, pd.DataFrame]) -> pd.DataFrame:
    """Telemetry DataFrame from short simulation."""
    return short_simulation[0]


@pytest.fixture
def events_df(short_simulation: Tuple[pd.DataFrame, pd.DataFrame]) -> pd.DataFrame:
    """Events DataFrame from short simulation."""
    return short_simulation[1]
