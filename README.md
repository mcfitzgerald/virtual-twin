# SimPy Production Line Digital Twin

**Version:** 0.3.1
**Frameworks:** SimPy, Pydantic, Pandas
**Scope:** Discrete Event Simulation (DES) & Synthetic Data Generation

## Overview

This software serves a dual purpose: it is an **Operational Simulator** for validating production line throughput and accumulation strategies, and a **Synthetic Data Generator** creating labeled datasets for Machine Learning (Predictive Maintenance and Process Mining).

The system models a high-speed Consumer Packaged Goods (CPG) line, accounting for physics (V-Curve rates), stochastic reliability (breakdowns/jams), and quality control (scrap rates).

## Quick Start

```bash
# Install dependencies
poetry install

# Run default simulation
poetry run python -m simpy_demo

# Run with CSV export
poetry run python -m simpy_demo --export

# Run specific config
poetry run python -m simpy_demo --run baseline_8hr --export
```

## Configuration System

The simulation uses a layered YAML configuration system:

```
config/
├── runs/           # Run parameters (duration, seed, start_time)
├── scenarios/      # What-if experiments (topology + equipment refs)
├── topologies/     # Line structure (station order, batch sizes)
├── equipment/      # Equipment parameters (uph, reliability, etc.)
└── materials/      # Material type definitions
```

### Example Run Config

```yaml
# config/runs/baseline_8hr.yaml
name: baseline_8hr
scenario: baseline
duration_hours: 8.0
random_seed: 42
telemetry_interval_sec: 1.0
start_time: "2025-01-06T06:00:00"  # Optional: ISO format, defaults to now()
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

Then create a run config pointing to it:

```yaml
# config/runs/high_buffer_8hr.yaml
name: high_buffer_8hr
scenario: high_buffer_test
duration_hours: 8.0
```

Run it:
```bash
poetry run python -m simpy_demo --run high_buffer_8hr --export
```

## Architecture

### Separation of Concerns

- **Run** → simulation parameters (duration, seed, start_time)
- **Scenario** → what-if experiment (topology + equipment + overrides)
- **Topology** → line structure (station order, batch sizes)
- **Equipment** → machine parameters (uph, reliability, quality)

### OEE Loss Mapping

| OEE Component | Config Parameter | Real-World Equivalent |
|---------------|------------------|----------------------|
| **Availability** | `reliability.mtbf_min` | Motor failure, cleaning |
| **Performance** | `performance.jam_prob` | Micro-stops, sensor misreads |
| **Quality** | `quality.defect_rate` | Fill variance, bad seals |

### Equipment 6-Phase Cycle

All machines use the same `Equipment` class - config determines behavior:

```
COLLECT → BREAKDOWN CHECK → MICROSTOP CHECK → EXECUTE → TRANSFORM → INSPECT/ROUTE
```

## Data Outputs

### Telemetry (`df_ts`)
- Time-series snapshots at configurable intervals
- Columns: `datetime`, `time`, buffer levels, machine states
- Use: Training ML models for predictive maintenance

### Event Log (`df_ev`)
- Transactional log of state changes
- Columns: `datetime`, `timestamp`, `machine`, `state`, `event_type`
- Use: OEE calculation, process mining

## CLI Options

```bash
python -m simpy_demo [OPTIONS]

Options:
  --run NAME      Run config name (default: baseline_8hr)
  --config PATH   Config directory (default: config)
  --export        Export results to CSV
  --output PATH   Output directory (default: output)
```

## Documentation

- [Architecture Diagrams](docs/architecture.md) - Mermaid diagrams of system design
- [CLAUDE.md](CLAUDE.md) - Development guide for AI assistants
- [CHANGELOG.md](CHANGELOG.md) - Version history
