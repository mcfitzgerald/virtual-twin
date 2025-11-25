# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SimPy-based discrete event simulation (DES) of a CPG (Consumer Packaged Goods) production line. The system serves as both an operational simulator for validating throughput/accumulation strategies and a synthetic data generator for ML training (predictive maintenance, process mining).

## Coding and Engineering Standards

Use `ruff` and `mypy` for linting, formatting, and typing

Use `semgrep` to find hardcodes

Use context7 to for library and package documentation (enabled via mcp)

Update `CHANGELOG.md` when comitting with git, use semantic versioning and also update version in `pyproject.toml`

## Commands

```bash
# Install dependencies
poetry install

# Run the simulation
poetry run python -m simpy_demo
```

## Architecture

### Module Structure

```
src/simpy_demo/
├── __init__.py      # Public API exports
├── __main__.py      # Entry point for `python -m simpy_demo`
├── models.py        # Pydantic schemas (MachineConfig, Product, grouped params)
├── equipment.py     # Equipment class (generic machine simulator)
├── topology.py      # Line structure definitions (CosmeticsLine, Station)
├── config.py        # Scenario configuration (ScenarioConfig, EquipmentParams)
├── baseline.py      # Default parameter values for equipment
├── engine.py        # SimulationEngine class (orchestration)
└── run.py           # Entry point with example usage
```

### Core Design: Separation of Concerns

The architecture separates:
1. **Topology** (line structure) from **Configuration** (parameters)
2. **Baseline** (defaults) from **Scenarios** (what-if experiments)
3. **Emergent behavior** driven by config (no separate behavior classes)

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
  - `Product` (Pydantic): Composite material pattern for traceability (Tube → Case → Pallet)
  - `MaterialType` (Enum): TUBE, CASE, PALLET, NONE

- **`topology.py`**:
  - `Station`: Defines structure only (name, batch_in, output_type)
  - `CosmeticsLine`: Line topology with stations list

- **`config.py`**:
  - `EquipmentParams`: Sparse overrides for what-if experiments
  - `ScenarioConfig`: Run parameters + equipment overrides dictionary

- **`baseline.py`**:
  - `BASELINE`: Default parameters for each station in CosmeticsLine

- **`equipment.py`**:
  - `Equipment`: Generic machine with 6-phase cycle: COLLECT → BREAKDOWN CHECK → MICROSTOP CHECK → EXECUTE → TRANSFORM → INSPECT/ROUTE

- **`engine.py`**:
  - `SimulationEngine`: Combines topology + baseline + scenario, builds layout, runs simulation

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
- **Telemetry (`df_ts`)**: Time-series snapshots (buffer levels, machine states) at 1-second intervals
- **Event Log (`df_ev`)**: State transition log for OEE calculation and process mining

## Configuration

Create custom `ScenarioConfig` instances for what-if experiments:

```python
from simpy_demo import ScenarioConfig, EquipmentParams, run_simulation

# Only specify overrides from baseline
scenario = ScenarioConfig(
    name="large_buffer_test",
    equipment={
        "Filler": EquipmentParams(buffer_capacity=500)
    }
)
run_simulation(scenario)
```

- Change `buffer_capacity` to test accumulation effects
- Adjust `reliability.mtbf_min` to test reliability impact
- Modify `uph` to break V-Curve balancing
