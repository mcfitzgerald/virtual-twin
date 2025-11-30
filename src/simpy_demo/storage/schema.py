"""DuckDB schema definitions for simulation results storage."""

SCHEMA_DDL = """
-- 1. SIMULATION_RUNS: Parent record for each simulation
CREATE TABLE IF NOT EXISTS simulation_runs (
    run_id INTEGER PRIMARY KEY,
    run_name VARCHAR NOT NULL,
    scenario_name VARCHAR NOT NULL,
    config_hash VARCHAR NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_hours DOUBLE NOT NULL,
    random_seed INTEGER,
    telemetry_interval_sec DOUBLE DEFAULT 300.0,
    -- Product context (denormalized)
    sku_name VARCHAR,
    sku_description VARCHAR,
    material_cost_per_pallet DOUBLE,
    selling_price_per_pallet DOUBLE,
    -- Config snapshot (JSON blob)
    config_snapshot JSON NOT NULL,
    -- Metadata
    git_commit VARCHAR,
    simpy_demo_version VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. TELEMETRY: Time-series data
CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_runs(run_id),
    ts TIMESTAMP NOT NULL,
    sim_time_sec DOUBLE NOT NULL,
    -- Production (incremental per interval)
    tubes_produced INTEGER DEFAULT 0,
    cases_produced INTEGER DEFAULT 0,
    pallets_produced INTEGER DEFAULT 0,
    good_pallets INTEGER DEFAULT 0,
    defective_pallets INTEGER DEFAULT 0,
    defects_created INTEGER DEFAULT 0,
    defects_detected INTEGER DEFAULT 0,
    -- Economics
    material_cost DOUBLE DEFAULT 0.0,
    conversion_cost DOUBLE DEFAULT 0.0,
    revenue DOUBLE DEFAULT 0.0,
    gross_margin DOUBLE DEFAULT 0.0,
    -- Dynamic data as JSON
    machine_states JSON,
    buffer_levels JSON
);

-- 3. MACHINE_TELEMETRY: Per-machine time-series (normalized)
CREATE TABLE IF NOT EXISTS machine_telemetry (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_runs(run_id),
    ts TIMESTAMP NOT NULL,
    sim_time_sec DOUBLE NOT NULL,
    machine_name VARCHAR NOT NULL,
    state VARCHAR NOT NULL,
    output_count INTEGER NOT NULL,
    buffer_level INTEGER,
    buffer_capacity INTEGER
);

-- 4. EVENTS: State transitions
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_runs(run_id),
    ts TIMESTAMP NOT NULL,
    sim_time_sec DOUBLE NOT NULL,
    machine_name VARCHAR NOT NULL,
    state VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    duration_sec DOUBLE
);

-- 5. RUN_SUMMARY: Pre-aggregated metrics
CREATE TABLE IF NOT EXISTS run_summary (
    run_id INTEGER PRIMARY KEY REFERENCES simulation_runs(run_id),
    total_tubes INTEGER DEFAULT 0,
    total_cases INTEGER DEFAULT 0,
    total_pallets INTEGER DEFAULT 0,
    total_good_pallets INTEGER DEFAULT 0,
    total_defective_pallets INTEGER DEFAULT 0,
    total_revenue DOUBLE DEFAULT 0.0,
    total_material_cost DOUBLE DEFAULT 0.0,
    total_conversion_cost DOUBLE DEFAULT 0.0,
    total_gross_margin DOUBLE DEFAULT 0.0,
    margin_percent DOUBLE,
    yield_percent DOUBLE,
    throughput_per_hour DOUBLE
);

-- 6. MACHINE_OEE: Pre-calculated OEE per machine
CREATE TABLE IF NOT EXISTS machine_oee (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_runs(run_id),
    machine_name VARCHAR NOT NULL,
    total_time_sec DOUBLE NOT NULL,
    execute_time_sec DOUBLE DEFAULT 0.0,
    starved_time_sec DOUBLE DEFAULT 0.0,
    blocked_time_sec DOUBLE DEFAULT 0.0,
    down_time_sec DOUBLE DEFAULT 0.0,
    jammed_time_sec DOUBLE DEFAULT 0.0,
    availability_percent DOUBLE,
    oee_percent DOUBLE,
    UNIQUE(run_id, machine_name)
);

-- 7. RUN_EQUIPMENT: Frozen equipment config per run
CREATE TABLE IF NOT EXISTS run_equipment (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_runs(run_id),
    machine_name VARCHAR NOT NULL,
    uph INTEGER NOT NULL,
    buffer_capacity INTEGER NOT NULL,
    mtbf_min DOUBLE,
    mttr_min DOUBLE,
    jam_prob DOUBLE,
    jam_time_sec DOUBLE,
    defect_rate DOUBLE,
    detection_prob DOUBLE,
    UNIQUE(run_id, machine_name)
);

-- Sequences for auto-increment IDs
CREATE SEQUENCE IF NOT EXISTS seq_telemetry_id START 1;
CREATE SEQUENCE IF NOT EXISTS seq_machine_telemetry_id START 1;
CREATE SEQUENCE IF NOT EXISTS seq_events_id START 1;
CREATE SEQUENCE IF NOT EXISTS seq_machine_oee_id START 1;
CREATE SEQUENCE IF NOT EXISTS seq_run_equipment_id START 1;
CREATE SEQUENCE IF NOT EXISTS seq_simulation_runs_id START 1;
"""

INDEX_DDL = """
-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_runs_started_at ON simulation_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_runs_scenario ON simulation_runs(scenario_name);
CREATE INDEX IF NOT EXISTS idx_telemetry_run_ts ON telemetry(run_id, ts);
CREATE INDEX IF NOT EXISTS idx_machine_telemetry_run_ts ON machine_telemetry(run_id, ts);
CREATE INDEX IF NOT EXISTS idx_machine_telemetry_machine ON machine_telemetry(run_id, machine_name);
CREATE INDEX IF NOT EXISTS idx_events_run_ts ON events(run_id, ts);
CREATE INDEX IF NOT EXISTS idx_events_machine ON events(run_id, machine_name);
"""

VIEW_DDL = """
-- Run comparison view
CREATE OR REPLACE VIEW v_run_comparison AS
SELECT r.run_id, r.run_name, r.scenario_name, r.sku_name, r.started_at,
       s.total_pallets, s.total_good_pallets, s.yield_percent,
       s.total_gross_margin, s.margin_percent, s.throughput_per_hour
FROM simulation_runs r
JOIN run_summary s ON r.run_id = s.run_id;

-- OEE by machine view
CREATE OR REPLACE VIEW v_machine_oee AS
SELECT r.run_name, r.scenario_name, r.started_at, m.*
FROM machine_oee m
JOIN simulation_runs r ON m.run_id = r.run_id;

-- Hourly production rollup
CREATE OR REPLACE VIEW v_hourly_production AS
SELECT run_id,
       date_trunc('hour', ts) as hour_bucket,
       SUM(pallets_produced) as pallets,
       SUM(good_pallets) as good,
       SUM(revenue) as revenue,
       SUM(gross_margin) as margin
FROM telemetry
GROUP BY run_id, date_trunc('hour', ts);

-- Cumulative production (DuckDB window functions)
CREATE OR REPLACE VIEW v_cumulative_production AS
SELECT run_id, ts,
       SUM(pallets_produced) OVER (PARTITION BY run_id ORDER BY ts) as cumulative_pallets,
       SUM(good_pallets) OVER (PARTITION BY run_id ORDER BY ts) as cumulative_good,
       SUM(gross_margin) OVER (PARTITION BY run_id ORDER BY ts) as cumulative_margin
FROM telemetry;
"""


def create_tables(conn) -> None:
    """Create all tables, indexes, and views in the database.

    Args:
        conn: DuckDB connection
    """
    conn.execute(SCHEMA_DDL)
    conn.execute(INDEX_DDL)
    conn.execute(VIEW_DDL)
