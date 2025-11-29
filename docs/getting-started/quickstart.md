# Quickstart

Run your first simulation in 5 minutes.

## Run the Baseline Simulation

```bash
poetry run python -m simpy_demo --run baseline_8hr --export
```

This runs an 8-hour simulation of a cosmetics packaging line and exports results to CSV.

### What You'll See

```
=== Configuration ===
Run: baseline_8hr
Scenario: baseline
Topology: cosmetics_line (4 stations)
Product: fresh_toothpaste_5oz
Duration: 8.0 hours

=== Simulation Running ===
...

=== Simulation Complete ===
Duration: 8.0 hours (28800.0 seconds)

Production:
  Tubes produced: 27,648
  Cases produced: 2,304
  Pallets produced: 384
  Good pallets: 372
  Defective pallets: 12

Economics:
  Material cost: $57,600.00
  Conversion cost: $12,800.00
  Revenue: $167,400.00
  Gross margin: $96,000.00 (57.4%)

OEE by Machine:
  Filler: 92.3%
  Inspector: 98.1%
  Packer: 94.5%
  Palletizer: 96.8%
```

## Check Your Results

The `--export` flag creates CSV files in the `output/` directory:

```bash
ls output/
```

```
telemetry_baseline_8hr_20250129_060000.csv
events_baseline_8hr_20250129_060000.csv
```

### Telemetry File

Time-series data captured every 5 minutes:

| Column | Description |
|--------|-------------|
| `datetime` | ISO timestamp |
| `time` | Simulation seconds |
| `tubes_produced` | Tubes produced this interval |
| `cases_produced` | Cases produced this interval |
| `pallets_produced` | Pallets produced this interval |
| `material_cost` | Material cost this interval |
| `conversion_cost` | Conversion cost this interval |
| `revenue` | Revenue this interval |
| `gross_margin` | Gross margin this interval |
| `Buf_Filler` | Filler buffer level |
| `Filler_state` | Filler machine state |

### Events File

State transition log for OEE calculation:

| Column | Description |
|--------|-------------|
| `datetime` | ISO timestamp |
| `timestamp` | Simulation seconds |
| `machine` | Equipment name |
| `state` | New state (STARVED, EXECUTE, DOWN, JAMMED, BLOCKED) |
| `event_type` | State transition identifier |
| `duration` | Time spent in previous state |

## Try a Different Run

List available run configs:

```bash
ls config/runs/
```

```
baseline_8hr.yaml
baseline_graph_8hr.yaml
```

Run the graph topology version:

```bash
poetry run python -m simpy_demo --run baseline_graph_8hr --export
```

## Create a Reproducible Run

Use the two-stage workflow for auditable, reproducible simulations:

```bash
# 1. Generate a scenario bundle
poetry run python -m simpy_demo configure --run baseline_8hr

# 2. Run the scenario
poetry run python -m simpy_demo simulate --scenario ./scenarios/baseline_8hr_*
```

The scenario bundle contains:

- `scenario.py` - Executable runner script
- `config_snapshot.yaml` - Frozen configuration
- `metadata.json` - Git commit, config hash, timestamp
- `output/` - Results after simulation

## Next Steps

- **[Concepts](concepts.md)** - Understand DES, OEE, and SimPy
- **[Configuration](../user-guide/configuration.md)** - Learn the YAML config system
- **[Basic Tutorial](../tutorials/basic-simulation.md)** - Detailed walkthrough
