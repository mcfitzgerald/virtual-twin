"""DuckDB storage module for simulation results.

This module provides persistence of simulation outputs to DuckDB,
enabling analytics and traceability via config snapshots.

Example usage:
    from virtual_twin.storage import save_results, connect

    # After running a simulation
    run_id = save_results(resolved, df_ts, df_ev)

    # Query results
    conn = connect()
    df = conn.execute("SELECT * FROM v_run_comparison").df()
"""

from pathlib import Path
from typing import TYPE_CHECKING

import duckdb

if TYPE_CHECKING:
    import pandas as pd

    from virtual_twin.loader import ResolvedConfig

DEFAULT_DB_PATH = Path("./virtual_twin_results.duckdb")


def save_results(
    resolved: "ResolvedConfig",
    df_ts: "pd.DataFrame",
    df_ev: "pd.DataFrame",
    db_path: Path | str | None = None,
) -> int:
    """Save simulation results to DuckDB.

    Args:
        resolved: Resolved configuration used for the simulation
        df_ts: Telemetry DataFrame (time-series)
        df_ev: Events DataFrame (state transitions)
        db_path: Path to database file (default: ./virtual_twin_results.duckdb)

    Returns:
        run_id of the stored simulation
    """
    from virtual_twin.storage.writer import DuckDBWriter

    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    writer = DuckDBWriter(path)
    try:
        return writer.store_run(resolved, df_ts, df_ev)
    finally:
        writer.close()


def get_db_path() -> Path:
    """Return the default database path."""
    return DEFAULT_DB_PATH


def connect(db_path: Path | str | None = None) -> duckdb.DuckDBPyConnection:
    """Get a DuckDB connection for queries.

    Args:
        db_path: Path to database file (default: ./virtual_twin_results.duckdb)

    Returns:
        DuckDB connection

    Example:
        conn = connect()
        df = conn.execute("SELECT * FROM v_run_comparison").df()
    """
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    return duckdb.connect(str(path))


__all__ = [
    "save_results",
    "get_db_path",
    "connect",
    "DEFAULT_DB_PATH",
]
