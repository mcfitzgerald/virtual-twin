# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SimPy-based discrete event simulation (DES) of a CPG (Consumer Packaged Goods) production line. The system serves as both an operational simulator for validating throughput/accumulation strategies and a synthetic data generator for ML training (predictive maintenance, process mining).

## Coding and Engineering Standards

Use `ruff` and `mypy` for linting, formatting, and typing

Use `semgrep` to find hardcodes

Use context7 to for library and package documentation (enabled via mcp)

Don't revinvent the wheel, search web for robust libraries and always opt for simple. Don't over-engineer!

Update `CHANGELOG.md` and `README.md` and any docs when comitting with git, use semantic versioning and also update version in `pyproject.toml`

## Commands

```bash
# Install dependencies
poetry install

# Run the simulation (default config)
poetry run python -m simpy_demo

# Run specific config
poetry run python -m simpy_demo --run baseline_8hr

# Export results to CSV
poetry run python -m simpy_demo --run baseline_8hr --export

# Use custom config directory
poetry run python -m simpy_demo --config ./my_configs --run custom_run
```

## Architecture

### Directory Structure

```
simpy-demo/
├── src/simpy_demo/
│   ├── __init__.py      # Public API exports
│   ├── __main__.py      # Entry point for `python -m simpy_demo`
│   ├── models.py        # Pydantic schemas (MachineConfig, Product, grouped params)
│   ├── equipment.py     # Equipment class (generic machine simulator)
│   ├── loader.py        # YAML config loader with name-based resolution
│   ├── config.py        # Re-exports from loader.py
│   ├── engine.py        # SimulationEngine class (orchestration)
│   └── run.py           # CLI entry point
├── config/
│   ├── runs/            # Run configs (duration, seed, scenario, product ref)
│   ├── scenarios/       # Scenario configs (topology + equipment refs)
│   ├── topologies/      # Line structure (station order, batch sizes)
│   ├── equipment/       # Equipment parameters + cost_rates
│   ├── products/        # Product/SKU definitions with economics
│   └── materials/       # Material type definitions
└── docs/
    └── architecture.md  # Mermaid diagrams of system architecture
```

### Core Design: Separation of Concerns

The architecture separates:
1. **Run** (simulation parameters) from **Scenario** (what-if experiments)
2. **Topology** (line structure) from **Equipment** (parameters)
3. **Emergent behavior** driven by config (no separate behavior classes)

### Configuration Hierarchy

```
Run → Scenario → Topology + Equipment[]
 └──→ Product (optional, for economics)
```

- **Run** (`config/runs/*.yaml`): Duration, random seed, telemetry interval, product reference
- **Scenario** (`config/scenarios/*.yaml`): References topology + equipment, defines overrides
- **Topology** (`config/topologies/*.yaml`): Station order, batch sizes, output types
- **Equipment** (`config/equipment/*.yaml`): UPH, buffer capacity, reliability/performance/quality params, cost_rates
- **Product** (`config/products/*.yaml`): SKU name, physical attributes, material_cost, selling_price

### Core Simulation Pattern
The system uses SimPy's cooperative multitasking with generator-based coroutines:
- **`simpy.Environment`**: Priority queue scheduler that advances time only on events
- **`Equipment`**: Python generators (`yield`) representing machines
- **`simpy.Store`**: Buffers for inter-machine synchronization; `yield store.get()` models starvation, `yield store.put()` models blocking

### Key Classes

- **`models.py`**:
  - `MachineConfig` (Pydantic): Complete machine config with grouped parameters
  - `ReliabilityParams`: MTBF/MTTR for availability loss
  - `PerformanceParams`: Jam probability/time for performance loss
  - `QualityParams`: Defect rate/detection for quality loss
  - `CostRates`: Labor, energy, overhead per hour for conversion cost
  - `ProductConfig`: SKU definition with physical and economic attributes
  - `Product` (Pydantic): Composite material pattern for traceability (Tube → Case → Pallet)
  - `MaterialType` (Enum): TUBE, CASE, PALLET, NONE

- **`loader.py`**:
  - `ConfigLoader`: Loads and resolves YAML configs by name
  - `RunConfig`, `ScenarioConfig`, `TopologyConfig`, `EquipmentConfig`: Dataclasses
  - `ResolvedConfig`: Fully resolved configuration ready for simulation

- **`equipment.py`**:
  - `Equipment`: Generic machine with 6-phase cycle: COLLECT → BREAKDOWN CHECK → MICROSTOP CHECK → EXECUTE → TRANSFORM → INSPECT/ROUTE

- **`engine.py`**:
  - `SimulationEngine`: Loads config, builds layout, runs simulation

### Equipment 6-Phase Cycle

All machines use the same `Equipment` class - config determines behavior:

```
PHASE 1: COLLECT        <- Always runs (wait for upstream material)
    |
PHASE 2: BREAKDOWN      <- Only if reliability.mtbf_min is set
    |                      - Poisson probability -> go DOWN
PHASE 3: MICROSTOP      <- Only if performance.jam_prob > 0
    |                      - Bernoulli per cycle -> JAMMED
PHASE 4: EXECUTE        <- Always runs (wait cycle_time_sec)
    |
PHASE 5: TRANSFORM      <- Based on output_type + quality.defect_rate
    |
PHASE 6: INSPECT/ROUTE  <- Only if quality.detection_prob > 0
```

### OEE Loss Mapping
- **Availability**: `reliability.mtbf_min`/`reliability.mttr_min` (time-based failures)
- **Performance**: `performance.jam_prob`/`performance.jam_time_sec` (cycle-based microstops)
- **Quality**: `quality.defect_rate`/`quality.detection_prob` (scrap routing)

### Data Outputs
- **Telemetry (`df_ts`)**: Time-series at 5-min intervals with **incremental** values per interval:
  - SKU context: `sku_name`, `sku_description`, `size_oz`, `units_per_case`, `cases_per_pallet`
  - Production (per interval): `tubes_produced`, `cases_produced`, `pallets_produced`, `good_pallets`, `defective_pallets`
  - Quality (per interval): `defects_created`, `defects_detected`
  - Economics (per interval): `material_cost`, `conversion_cost`, `revenue`, `gross_margin`
  - Snapshots: Buffer levels, machine states
- **Event Log (`df_ev`)**: State transition log for OEE calculation and process mining

### Economic Model
- **Material cost** = pallets produced × `product.material_cost` (includes scrap)
- **Conversion cost** = Σ(machine wall-clock time × `equipment.cost_rates`) - responsive to OEE
- **Revenue** = good pallets × `product.selling_price`
- **Gross margin** = revenue - material_cost - conversion_cost

## Configuration

### YAML-Based Configuration

Create what-if experiments by creating new YAML files:

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

```yaml
# config/runs/high_buffer_8hr.yaml
name: high_buffer_8hr
scenario: high_buffer_test
product: fresh_toothpaste_5oz  # Optional: enables economic tracking
duration_hours: 8.0
random_seed: 42
telemetry_interval_sec: 300.0  # 5-minute intervals
```

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

Then run:
```bash
poetry run python -m simpy_demo --run high_buffer_8hr
```

### Programmatic Usage

```python
from simpy_demo import SimulationEngine, ConfigLoader

# Using YAML configs
engine = SimulationEngine("config")
df_ts, df_ev = engine.run("baseline_8hr")

# Or load and modify configs programmatically
loader = ConfigLoader("config")
resolved = loader.resolve_run("baseline_8hr")
# Modify resolved.equipment["Filler"].buffer_capacity = 500
machine_configs = loader.build_machine_configs(resolved)
```

### What-If Experiments

- Change `buffer_capacity` to test accumulation effects
- Adjust `reliability.mtbf_min` to test reliability impact
- Modify `uph` to break V-Curve balancing
- Add scenario `overrides` for targeted parameter changes
