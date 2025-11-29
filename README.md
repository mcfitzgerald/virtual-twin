# SimPy Production Line Digital Twin

**Version:** 0.9.0
**Frameworks:** SimPy, Pydantic, Pandas
**Scope:** Discrete Event Simulation (DES) & Synthetic Data Generation

## Overview

This software serves a dual purpose: it is an **Operational Simulator** for validating production line throughput and accumulation strategies, and a **Synthetic Data Generator** creating labeled datasets for Machine Learning (Predictive Maintenance and Process Mining).

The system models a high-speed Consumer Packaged Goods (CPG) line, accounting for physics (V-Curve rates), stochastic reliability (breakdowns/jams), quality control (scrap rates), and **economic tracking** (material costs, conversion costs, revenue).

## Quick Start

```bash
# Install dependencies
poetry install

# Run default simulation
poetry run python -m simpy_demo

# Run with CSV export
poetry run python -m simpy_demo --run baseline_8hr --export

# Two-stage workflow (reproducible scenario bundles)
poetry run python -m simpy_demo configure --run baseline_8hr
poetry run python -m simpy_demo simulate --scenario ./scenarios/baseline_8hr_*
```

## Configuration System

The simulation uses a layered YAML configuration system:

```
config/
├── runs/           # Run parameters (duration, seed, product ref)
├── scenarios/      # What-if experiments (topology + equipment refs)
├── topologies/     # Line structure (linear or DAG graph)
├── equipment/      # Equipment parameters (uph, reliability, cost_rates)
├── products/       # SKU definitions with economics
├── behaviors/      # Phase definitions (optional, has defaults)
├── sources/        # Source store configuration
├── defaults.yaml   # Global default values
└── constants.yaml  # Named constants for substitution
```

### Example Run Config

```yaml
# config/runs/baseline_8hr.yaml
name: baseline_8hr
scenario: baseline
product: fresh_toothpaste_5oz  # Optional: enables economic tracking
duration_hours: 8.0
random_seed: 42
telemetry_interval_sec: 300.0  # 5-minute intervals
start_time: "2025-01-06T06:00:00"
```

### Example Product Config

```yaml
# config/products/fresh_toothpaste_5oz.yaml
name: fresh_toothpaste_5oz
description: "Fresh Toothpaste 5oz Tube"
size_oz: 5.0
units_per_case: 12
cases_per_pallet: 60
material_cost: 150.00   # $ per pallet
selling_price: 450.00   # $ per pallet
```

### Creating What-If Experiments

Create a new scenario with overrides:

```yaml
# config/scenarios/high_buffer_test.yaml
name: high_buffer_test
topology: cosmetics_line
equipment:
  - Filler
  - Inspector
  - Packer
  - Palletizer
overrides:
  Filler:
    buffer_capacity: 500
```

Then create a run config and execute:
```bash
poetry run python -m simpy_demo --run high_buffer_8hr --export
```

## Architecture

### Key Components

- **BehaviorOrchestrator**: Pluggable 6-phase equipment cycle defined in YAML
- **TopologyGraph**: Supports linear chains and DAG-based layouts with conditional routing
- **LayoutBuilder**: Constructs SimPy environment from topology graphs
- **ScenarioGenerator**: Creates reproducible scenario bundles

### Equipment 6-Phase Cycle

All machines use the same `Equipment` class with configurable behavior:

```
COLLECT → BREAKDOWN CHECK → MICROSTOP CHECK → EXECUTE → TRANSFORM → INSPECT/ROUTE
```

### OEE Loss Mapping

| OEE Component | Config Parameter | Real-World Equivalent |
|---------------|------------------|----------------------|
| **Availability** | `reliability.mtbf_min` | Motor failure, cleaning |
| **Performance** | `performance.jam_prob` | Micro-stops, sensor misreads |
| **Quality** | `quality.defect_rate` | Fill variance, bad seals |

### Economic Model

- **Material cost** = pallets produced × `product.material_cost`
- **Conversion cost** = Σ(machine time × `equipment.cost_rates`)
- **Revenue** = good pallets × `product.selling_price`
- **Gross margin** = revenue - material_cost - conversion_cost

## Data Outputs

### Telemetry (`df_telemetry`)
- Time-series snapshots at configurable intervals (default 5 min)
- **Incremental values** per interval (not cumulative)
- Columns: `datetime`, `time`, production counts, economics, buffer levels, machine states
- Use: Training ML models for predictive maintenance

### Event Log (`df_events`)
- Transactional log of state changes
- Columns: `datetime`, `timestamp`, `machine`, `state`, `event_type`, `duration`
- Use: OEE calculation, process mining

### Summary (`summary.json`)
- Production totals, economics, OEE by machine
- Generated with `simulate` command

## CLI Commands

```bash
# Direct run (legacy, still works)
python -m simpy_demo --run baseline_8hr --export

# Subcommand: run
python -m simpy_demo run --run baseline_8hr --export

# Subcommand: configure (generate scenario bundle)
python -m simpy_demo configure --run baseline_8hr
python -m simpy_demo configure --run baseline_8hr --dry-run

# Subcommand: simulate (run from scenario bundle)
python -m simpy_demo simulate --scenario ./scenarios/baseline_8hr_20251129_143022

# Options
  --run NAME      Run config name (default: baseline_8hr)
  --config PATH   Config directory (default: config)
  --export        Export results to CSV
  --output PATH   Output directory (default: output)
```

## Scenario Bundles

The `configure` command generates reproducible scenario bundles:

```
scenarios/baseline_8hr_20251129_143022/
├── scenario.py           # Executable runner script
├── config_snapshot.yaml  # Frozen resolved configuration
├── metadata.json         # Git commit, config hash, version
└── output/               # Results after simulate
    ├── telemetry.csv
    ├── events.csv
    └── summary.json
```

Benefits:
- **Reproducibility**: Config snapshot captures entire state
- **Auditing**: Config hash ties results to configuration
- **Version tracking**: Git commit recorded in metadata

## Documentation

- [Architecture Diagrams](docs/architecture.md) - Mermaid diagrams of system design
- [CLAUDE.md](CLAUDE.md) - Development guide for AI assistants
- [CHANGELOG.md](CHANGELOG.md) - Version history
