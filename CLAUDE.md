# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SimPy-based discrete event simulation (DES) of a CPG (Consumer Packaged Goods) production line. The system serves as both an operational simulator for validating throughput/accumulation strategies and a synthetic data generator for ML training (predictive maintenance, process mining).

## Coding and Engineering Standards

Use `ruff` and `mypy` for linting, formatting, and typing

Use `semgrep` to find hardcodes

Always use context7 when I need code generation, setup or configuration steps, or
library/API documentation. This means you should automatically use the Context7 MCP
tools to resolve library id and get library docs without me having to explicitly ask.

Don't reinvent the wheel, search web for robust libraries and always opt for simple. Don't over-engineer!

Update `CHANGELOG.md` and `README.md` and `docs/` when committing with git, use semantic versioning and also update version in `pyproject.toml`

## Commands

```bash
# Install dependencies
poetry install

# Run simulation (default or named config)
poetry run python -m simpy_demo
poetry run python -m simpy_demo --run baseline_8hr --export

# Two-stage workflow (reproducible scenario bundles)
poetry run python -m simpy_demo configure --run baseline_8hr
poetry run python -m simpy_demo simulate --scenario ./scenarios/baseline_8hr_*

# Linting and type checking
poetry run ruff check src/
poetry run ruff format src/
poetry run mypy src/

# Documentation (local dev server)
poetry run mkdocs serve
poetry run mkdocs build
```

## Architecture

### Directory Structure

```
simpy-demo/
├── src/simpy_demo/
│   ├── __init__.py           # Public API exports
│   ├── __main__.py           # Entry point for `python -m simpy_demo`
│   ├── models.py             # Pydantic schemas (MachineConfig, Product, params)
│   ├── equipment.py          # Equipment class (generic machine simulator)
│   ├── loader.py             # YAML config loader with name-based resolution
│   ├── engine.py             # SimulationEngine class (orchestration)
│   ├── behavior/             # Pluggable 6-phase equipment behavior
│   │   ├── orchestrator.py   # BehaviorOrchestrator (phase sequencing)
│   │   └── phases/           # Phase implementations (collect, breakdown, etc.)
│   ├── topology/             # DAG-based production line structure
│   │   └── graph.py          # TopologyGraph (branching, merging, routing)
│   ├── simulation/           # Runtime execution
│   │   ├── layout.py         # LayoutBuilder (SimPy stores from topology)
│   │   └── runtime.py        # execute_scenario() for bundles
│   ├── cli/                  # Subcommands (configure, simulate)
│   └── codegen/              # ScenarioGenerator (Jinja2 templates)
├── config/
│   ├── runs/                 # Run configs (duration, seed, scenario, product ref)
│   ├── scenarios/            # Scenario configs (topology + equipment refs)
│   ├── topologies/           # Line structure (linear or DAG graph)
│   ├── equipment/            # Equipment parameters + cost_rates
│   ├── products/             # Product/SKU definitions with economics
│   └── sources/              # Source store configuration
└── docs/                     # MkDocs documentation site
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

- **`models.py`**: Pydantic schemas
  - `MachineConfig`: Complete machine config with grouped OEE parameters
  - `ReliabilityParams`, `PerformanceParams`, `QualityParams`: OEE loss parameters
  - `CostRates`: Labor, energy, overhead per hour for conversion cost
  - `ProductConfig`: SKU definition with physical and economic attributes
  - `Product`: Composite material with traceability (Tube → Case → Pallet)

- **`loader.py`**: YAML config loading
  - `ConfigLoader`: Loads and resolves configs by name
  - `ResolvedConfig`: Fully resolved configuration ready for simulation

- **`equipment.py`**: `Equipment` class - generic machine using BehaviorOrchestrator

- **`engine.py`**: `SimulationEngine` - loads config, builds layout, runs simulation

- **`behavior/orchestrator.py`**: `BehaviorOrchestrator` - sequences phase execution
  - Phases: CollectPhase, BreakdownPhase, MicrostopPhase, ExecutePhase, TransformPhase, InspectPhase

- **`topology/graph.py`**: `TopologyGraph` - DAG-based line structure
  - Supports branching, merging, conditional routing (quality gates)
  - Special nodes: `_source`, `_sink`, `_reject`

- **`simulation/layout.py`**: `LayoutBuilder` - creates SimPy stores and Equipment from TopologyGraph

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
