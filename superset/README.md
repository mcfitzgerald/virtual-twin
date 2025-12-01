# Virtual Twin Superset Dashboards

Pre-built Apache Superset dashboards for Virtual Twin simulation analytics.

## Contents

- **3 Dashboards**: Executive Summary, OEE Deep Dive, Production Analysis
- **15 Charts**: Tables, bar charts, time series, pie charts
- **5 Datasets**: Run comparison, OEE, telemetry, state summary, machine telemetry
- **1 Database**: DuckDB connection configuration

## Quick Import

1. In Superset, go to **Settings** → **Import Dashboard**
2. Upload `virtual_twin_dashboards.zip`
3. Review and click **Import**

> **Note**: The database connection URI is set to `duckdb:////data/virtual-twin/virtual_twin_results.duckdb` (Docker mount path). You may need to update this after import if using a different path.

## Dashboards

### Executive Summary
- Run Comparison Table
- Yield by Run
- Gross Margin by Run
- Throughput by Run

### OEE Deep Dive
- OEE by Machine (horizontal bar)
- Availability by Machine
- State Time Breakdown (stacked bar)
- Loss Time Pareto (pie)

### Production Analysis
- Production Over Time
- Cumulative Production
- Revenue vs Cost
- Gross Margin Over Time
- Buffer Levels by Machine
- Defects Over Time

## Manual Import (Alternative)

If the ZIP import fails, you can manually:

1. Add the database connection first (Settings → Database Connections)
2. Create datasets from tables/views
3. Import individual charts
4. Build dashboards from imported charts

## File Structure

```
superset/
├── virtual_twin_dashboards.zip  # Ready-to-import bundle
├── metadata.yaml                # Export metadata
├── databases/
│   └── DuckDB.yaml             # Database connection
├── datasets/
│   └── virtual_twin_results/
│       ├── v_run_comparison.yaml
│       ├── v_machine_oee.yaml
│       ├── telemetry.yaml
│       ├── state_summary.yaml
│       └── machine_telemetry.yaml
├── charts/
│   ├── run_comparison_table.yaml
│   ├── yield_by_run.yaml
│   ├── ... (15 charts)
└── dashboards/
    ├── executive_summary.yaml
    ├── oee_deep_dive.yaml
    └── production_analysis.yaml
```

## Customization

Edit the YAML files to customize:
- Column names and labels
- Chart types and styling
- Dashboard layouts
- Metrics and calculations

Then recreate the ZIP:
```bash
cd superset
zip -r virtual_twin_dashboards.zip metadata.yaml databases/ datasets/ charts/ dashboards/
```
