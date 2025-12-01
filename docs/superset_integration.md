# Apache Superset Integration Plan

This document outlines the strategy for integrating Virtual Twin simulation results with Apache Superset for deep-dive analytics and visualization.

## Why Superset over Grafana?

| Aspect | Grafana | Superset |
|--------|---------|----------|
| **Primary Use** | Real-time monitoring | Ad-hoc analytics |
| **Query Interface** | Pre-built panels | SQL Lab exploration |
| **Drill-down** | Limited | Rich filtering & pivoting |
| **Chart Types** | Time-series focused | 40+ visualization types |
| **Data Exploration** | Dashboard-centric | Dataset-centric |

Superset is better suited for:
- Comparing multiple simulation runs
- Root cause analysis of OEE losses
- What-if scenario exploration
- Building executive summaries

---

## Prerequisites

### 1. Superset Installation
User already has Superset running locally.

### 2. Required Python Packages
Superset needs DuckDB support installed in its Python environment:

```bash
pip install duckdb duckdb-engine
```

**Package versions (tested):**
- `duckdb >= 1.0.0`
- `duckdb-engine >= 0.13.0`

### 3. Docker Users
If running Superset via Docker, extend the official image:

```dockerfile
FROM apache/superset:4.1.1
USER root
RUN pip install duckdb==1.1.3 duckdb-engine==0.15.0
USER superset
```

---

## Connection Configuration

### SQLAlchemy URI

For a local DuckDB file:
```
duckdb:////Users/michael/Documents/Github/virtual-twin/virtual_twin_results.duckdb
```

Note: Four slashes (`////`) for absolute paths on Unix.

### Engine Parameters (Critical)

Configure in **Advanced → Other → Engine Parameters**:

```json
{
  "connect_args": {
    "read_only": true,
    "config": {
      "threads": 4
    }
  }
}
```

**Why `read_only: true` is critical:**
- DuckDB allows only ONE read-write connection at a time
- Without read-only mode, concurrent dashboard queries will cause locks
- Superset fires multiple queries simultaneously (one per chart/filter)
- Read-only mode allows unlimited concurrent readers

### Connection Testing

After configuration, use SQL Lab to verify:
```sql
SELECT * FROM simulation_runs LIMIT 5;
```

---

## Database Schema Overview

Virtual Twin provides these tables/views for analytics:

### Core Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `simulation_runs` | Run metadata | `run_id`, `run_name`, `scenario_name`, `config_snapshot` |
| `run_summary` | Aggregated KPIs | `total_pallets`, `yield_percent`, `gross_margin` |
| `machine_oee` | Per-machine OEE | `machine_name`, `oee_percent`, `availability_percent` |
| `telemetry` | Time-series (5-min) | `ts`, production counts, economics |
| `machine_telemetry` | Per-machine time-series | `machine_name`, `state`, `buffer_level` |
| `state_summary` | Bucketed state durations | `execute_sec`, `down_sec`, `jammed_sec` |

### Pre-built Views

| View | Use Case |
|------|----------|
| `v_run_comparison` | Compare runs side-by-side |
| `v_machine_oee` | OEE analysis with run context |
| `v_hourly_production` | Hourly rollups |
| `v_cumulative_production` | Cumulative trends |
| `v_oee_from_summary` | OEE from pre-aggregated data |

---

## Recommended Datasets

Create these Superset datasets for analytics:

### 1. Run Comparison Dataset
**Source:** `v_run_comparison`
**Use:** Executive summary, scenario comparison

### 2. Machine OEE Dataset
**Source:** `v_machine_oee`
**Use:** OEE breakdown, bottleneck identification

### 3. Production Time Series Dataset
**Source:** `telemetry` joined with `simulation_runs`
**Use:** Trend analysis, cumulative charts

### 4. State Analysis Dataset
**Source:** `state_summary` joined with `simulation_runs`
**Use:** Loss attribution, Pareto analysis

### 5. Machine State Timeline Dataset
**Source:** `machine_telemetry`
**Use:** Buffer analysis, state transitions

---

## Proposed Dashboard Structure

### Dashboard 1: Executive Summary
**Audience:** Management
**Refresh:** On-demand

| Chart | Type | Dataset |
|-------|------|---------|
| Run Comparison Table | Table | `v_run_comparison` |
| Yield % by Scenario | Bar Chart | `v_run_comparison` |
| Margin Trend | Line Chart | `v_run_comparison` |
| Best/Worst Runs | Big Number | `run_summary` |

### Dashboard 2: OEE Deep Dive
**Audience:** Operations, Engineers
**Refresh:** On-demand

| Chart | Type | Dataset |
|-------|------|---------|
| OEE by Machine | Horizontal Bar | `v_machine_oee` |
| Availability vs Performance | Scatter Plot | `machine_oee` |
| State Time Breakdown | Stacked Bar | `state_summary` |
| Loss Pareto | Pie/Treemap | `machine_oee` |
| OEE Heatmap (Run × Machine) | Heatmap | `machine_oee` |

### Dashboard 3: Production Analysis
**Audience:** Planning, Operations
**Refresh:** On-demand

| Chart | Type | Dataset |
|-------|------|---------|
| Cumulative Production | Area Chart | `v_cumulative_production` |
| Hourly Throughput | Bar Chart | `v_hourly_production` |
| Revenue vs Cost | Dual-Axis Line | `telemetry` |
| Buffer Utilization | Line Chart | `machine_telemetry` |

### Dashboard 4: What-If Scenarios
**Audience:** Engineers, Analysts
**Refresh:** On-demand

| Chart | Type | Dataset |
|-------|------|---------|
| Scenario Filter | Filter Box | `simulation_runs` |
| Parameter Comparison | Table | `run_equipment` |
| Impact Analysis | Waterfall | Custom SQL |
| Sensitivity Chart | Line Chart | Custom SQL |

### Dashboard 5: Time Series Explorer
**Audience:** Engineers, Analysts
**Refresh:** On-demand

| Chart | Type | Dataset |
|-------|------|---------|
| Production Over Time | Time-series Line | `telemetry` |
| Machine States Timeline | Mixed Timeseries | `machine_telemetry` |
| Buffer Levels | Multi-line | `machine_telemetry` |
| Cumulative Economics | Area Chart | `telemetry` |
| State Transitions | Event Annotation | `events_detail` |
| Defect Rate Over Time | Line Chart | `telemetry` |

### Dashboard 6: Event Analysis (Debug Mode)
**Audience:** Engineers (requires `--debug-events` runs)
**Refresh:** On-demand

| Chart | Type | Dataset |
|-------|------|---------|
| Event Timeline | Gantt/Timeline | `events` |
| State Duration Distribution | Histogram | `events` |
| Failure Events | Table | `events_detail` |
| MTBF/MTTR Analysis | Big Number + Line | `events_detail` |

---

## Time Series Datasets

### Telemetry Time Series
**Table:** `telemetry`
**Temporal Column:** `ts`
**Grain:** 5-minute intervals

Key metrics for time series:
- `tubes_produced`, `cases_produced`, `pallets_produced` (incremental)
- `good_pallets`, `defective_pallets`
- `defects_created`, `defects_detected`
- `material_cost`, `conversion_cost`, `revenue`, `gross_margin`

**Example chart:** Cumulative production with running totals
```sql
SELECT
    ts,
    SUM(pallets_produced) OVER (ORDER BY ts) AS cumulative_pallets,
    SUM(good_pallets) OVER (ORDER BY ts) AS cumulative_good,
    SUM(gross_margin) OVER (ORDER BY ts) AS cumulative_margin
FROM telemetry
WHERE run_id = {{ run_id }}
ORDER BY ts;
```

### Machine Telemetry Time Series
**Table:** `machine_telemetry`
**Temporal Column:** `ts`
**Grain:** 5-minute intervals

Key metrics:
- `state` (categorical: EXECUTE, STARVED, BLOCKED, DOWN, JAMMED)
- `buffer_level` (integer)
- `output_count` (cumulative per machine)

**Example chart:** Buffer levels by machine
```sql
SELECT
    ts,
    machine_name,
    buffer_level,
    buffer_capacity
FROM machine_telemetry
WHERE run_id = {{ run_id }}
ORDER BY ts, machine_name;
```

### State Summary Time Series
**Table:** `state_summary`
**Temporal Column:** `bucket_start_ts`
**Grain:** 5-minute buckets

Pre-aggregated state durations per bucket:
- `execute_sec`, `starved_sec`, `blocked_sec`, `down_sec`, `jammed_sec`
- `availability_pct` (pre-computed)
- `down_count`, `jammed_count` (event counts)

**Example chart:** Availability over time by machine
```sql
SELECT
    bucket_start_ts AS ts,
    machine_name,
    availability_pct
FROM state_summary
WHERE run_id = {{ run_id }}
ORDER BY bucket_start_ts, machine_name;
```

### Events Detail (Filtered)
**Table:** `events_detail`
**Temporal Column:** `ts`
**Grain:** Event-level (sparse)

Contains only "interesting" events (DOWN, JAMMED transitions):
- `state`, `prev_state`
- `duration_sec`
- `is_interesting`

**Example chart:** Downtime events timeline
```sql
SELECT
    ts,
    machine_name,
    state,
    duration_sec
FROM events_detail
WHERE run_id = {{ run_id }}
  AND state IN ('DOWN', 'JAMMED')
ORDER BY ts;
```

### Full Events (Debug Mode Only)
**Table:** `events`
**Temporal Column:** `ts`
**Note:** Only populated with `--debug-events` flag

Complete state transition log for deep debugging:
- Every state change recorded
- ~600k rows per 8-hour simulation

---

## Exploratory Analysis with SQL Lab

Superset's SQL Lab is ideal for ad-hoc exploration before building dashboards.

### SQL Lab Best Practices

1. **Start with views** - Use `v_*` views for quick exploration
2. **Filter by run_id** - Always include `WHERE run_id = X` to scope analysis
3. **Use CTEs** - Break complex queries into readable parts
4. **Save queries** - Save useful queries for reuse and sharing
5. **Create charts** - Promote SQL Lab queries directly to charts

### Exploratory Query Templates

#### 1. Run Overview
```sql
-- Quick summary of a specific run
SELECT
    r.run_name,
    r.scenario_name,
    r.duration_hours,
    s.total_pallets,
    s.total_good_pallets,
    s.yield_percent,
    s.total_gross_margin,
    s.throughput_per_hour
FROM simulation_runs r
JOIN run_summary s ON r.run_id = s.run_id
WHERE r.run_id = {{ run_id }};
```

#### 2. Machine Performance Ranking
```sql
-- Rank machines by OEE within a run
SELECT
    machine_name,
    oee_percent,
    availability_percent,
    execute_time_sec / total_time_sec * 100 AS utilization_pct,
    RANK() OVER (ORDER BY oee_percent DESC) AS oee_rank
FROM machine_oee
WHERE run_id = {{ run_id }}
ORDER BY oee_rank;
```

#### 3. Hourly Trend Analysis
```sql
-- Analyze production patterns by hour
SELECT
    EXTRACT(HOUR FROM ts) AS hour_of_day,
    AVG(pallets_produced) AS avg_pallets,
    SUM(pallets_produced) AS total_pallets,
    AVG(gross_margin) AS avg_margin
FROM telemetry
WHERE run_id = {{ run_id }}
GROUP BY 1
ORDER BY 1;
```

#### 4. State Distribution by Machine
```sql
-- How much time did each machine spend in each state?
SELECT
    machine_name,
    ROUND(execute_time_sec / total_time_sec * 100, 1) AS pct_execute,
    ROUND(starved_time_sec / total_time_sec * 100, 1) AS pct_starved,
    ROUND(blocked_time_sec / total_time_sec * 100, 1) AS pct_blocked,
    ROUND(down_time_sec / total_time_sec * 100, 1) AS pct_down,
    ROUND(jammed_time_sec / total_time_sec * 100, 1) AS pct_jammed
FROM machine_oee
WHERE run_id = {{ run_id }}
ORDER BY machine_name;
```

#### 5. Cross-Run Comparison
```sql
-- Compare key metrics across multiple runs
SELECT
    run_name,
    scenario_name,
    total_good_pallets,
    yield_percent,
    margin_percent,
    throughput_per_hour
FROM v_run_comparison
WHERE run_id IN ({{ run_ids }})
ORDER BY total_good_pallets DESC;
```

#### 6. Bottleneck Detection
```sql
-- Find the constraint machine
SELECT
    machine_name,
    starved_time_sec AS waiting_for_input,
    blocked_time_sec AS waiting_for_output,
    CASE
        WHEN starved_time_sec < blocked_time_sec THEN 'Potential Bottleneck (blocking downstream)'
        WHEN starved_time_sec > blocked_time_sec THEN 'Starved (upstream is bottleneck)'
        ELSE 'Balanced'
    END AS diagnosis
FROM machine_oee
WHERE run_id = {{ run_id }}
ORDER BY blocked_time_sec DESC;
```

#### 7. Economic Efficiency
```sql
-- Revenue per machine-hour
WITH machine_time AS (
    SELECT
        SUM(total_time_sec) / 3600.0 AS total_machine_hours
    FROM machine_oee
    WHERE run_id = {{ run_id }}
)
SELECT
    r.run_name,
    s.total_revenue,
    s.total_gross_margin,
    mt.total_machine_hours,
    s.total_revenue / mt.total_machine_hours AS revenue_per_machine_hour,
    s.total_gross_margin / mt.total_machine_hours AS margin_per_machine_hour
FROM run_summary s
JOIN simulation_runs r ON s.run_id = r.run_id
CROSS JOIN machine_time mt
WHERE s.run_id = {{ run_id }};
```

#### 8. Defect Flow Analysis
```sql
-- Track defects through the line
SELECT
    ts,
    SUM(defects_created) OVER (ORDER BY ts) AS cumulative_created,
    SUM(defects_detected) OVER (ORDER BY ts) AS cumulative_detected,
    SUM(defects_created - defects_detected) OVER (ORDER BY ts) AS cumulative_escaped
FROM telemetry
WHERE run_id = {{ run_id }}
ORDER BY ts;
```

### Using Jinja Templates

Superset supports Jinja templating for dynamic queries:

```sql
-- Filter by selected run(s) from dashboard filter
SELECT * FROM telemetry
WHERE run_id IN ({{ filter_values('run_id') | join(', ') }})

-- Use dashboard time range
WHERE ts >= '{{ from_dttm }}' AND ts < '{{ to_dttm }}'

-- Current user context
WHERE created_by = '{{ current_username() }}'
```

### Promoting Queries to Charts

1. Write and test query in SQL Lab
2. Click **Create Chart** button
3. Select visualization type
4. Configure chart options
5. Save to dashboard

---

## Implementation Steps

### Phase 1: Connection Setup
1. Install `duckdb` and `duckdb-engine` in Superset environment
2. Add DuckDB database connection with read-only mode
3. Test connection via SQL Lab

### Phase 2: Dataset Creation
1. Create datasets for each view/table listed above
2. Define calculated columns where needed
3. Set up semantic layer (column labels, descriptions)

### Phase 3: Core Dashboards
1. Build Executive Summary dashboard
2. Build OEE Deep Dive dashboard
3. Add cross-filtering between charts

### Phase 4: Advanced Analytics
1. Create Production Analysis dashboard
2. Build What-If Scenarios dashboard
3. Add custom SQL charts for complex analysis

### Phase 5: Polish & Documentation
1. Add dashboard descriptions and help text
2. Set up row-level security if needed
3. Configure caching for common queries
4. Export dashboards for version control

---

## Performance Considerations

### Query Optimization
- Use pre-built views (`v_*`) instead of raw tables where possible
- Limit time ranges in filters to reduce data scanned
- Avoid `SELECT *` in custom SQL

### Caching Strategy
- Enable Superset's query cache (Redis recommended)
- Set 1-hour cache for simulation data (it's historical, not real-time)
- Use "Force refresh" for updated runs

### Concurrency
- **Always use read-only mode** in connection settings
- Limit concurrent dashboard users if experiencing locks
- Consider separate DuckDB file for Superset if running simulations frequently

---

## Useful SQL Queries for SQL Lab

### Compare Two Scenarios
```sql
SELECT
    run_name,
    scenario_name,
    total_good_pallets,
    yield_percent,
    total_gross_margin,
    margin_percent
FROM v_run_comparison
WHERE scenario_name IN ('baseline', 'high_buffer_test')
ORDER BY started_at DESC;
```

### OEE Loss Attribution
```sql
SELECT
    machine_name,
    down_time_sec / 3600.0 AS down_hours,
    jammed_time_sec / 3600.0 AS jammed_hours,
    starved_time_sec / 3600.0 AS starved_hours,
    blocked_time_sec / 3600.0 AS blocked_hours
FROM machine_oee
WHERE run_id = (SELECT MAX(run_id) FROM simulation_runs)
ORDER BY down_time_sec DESC;
```

### Bottleneck Identification
```sql
SELECT
    machine_name,
    starved_time_sec AS upstream_issue,
    blocked_time_sec AS downstream_issue,
    CASE
        WHEN starved_time_sec > blocked_time_sec THEN 'Starved (upstream slow)'
        WHEN blocked_time_sec > starved_time_sec THEN 'Blocked (downstream slow)'
        ELSE 'Balanced'
    END AS bottleneck_type
FROM machine_oee
WHERE run_id = ?;
```

### Economic Impact by Hour
```sql
SELECT
    date_trunc('hour', ts) AS hour,
    SUM(revenue) AS hourly_revenue,
    SUM(material_cost + conversion_cost) AS hourly_cost,
    SUM(gross_margin) AS hourly_margin
FROM telemetry
WHERE run_id = ?
GROUP BY 1
ORDER BY 1;
```

---

## References

- [Apache Superset Documentation](https://superset.apache.org/docs/)
- [DuckDB + Superset Blog](https://blog.nobugware.com/post/2025/duckdb-with-apache-superset/)
- [MotherDuck Superset Integration](https://motherduck.com/docs/integrations/bi-tools/superset-preset/)
- [DuckDB Concurrency](https://duckdb.org/docs/stable/connect/concurrency)
- [Superset Dashboard Best Practices](https://preset.io/blog/the-data-engineers-guide-to-lightning-fast-apache-superset-dashboards/)
- [Superset-DuckDB GitHub](https://github.com/jorritsandbrink/superset-duckdb)

---

## Next Steps

After following this plan:
1. [ ] Install duckdb-engine in Superset
2. [ ] Configure DuckDB connection with read-only mode
3. [ ] Create datasets from views
4. [ ] Build Executive Summary dashboard
5. [ ] Build OEE Deep Dive dashboard
6. [ ] Document and share with team
