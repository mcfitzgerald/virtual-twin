# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SimPy-based discrete event simulation (DES) of a CPG (Consumer Packaged Goods) production line. The system serves as both an operational simulator for validating throughput/accumulation strategies and a synthetic data generator for ML training (predictive maintenance, process mining).

## Commands

```bash
# Install dependencies
poetry install

# Run the simulation
poetry run python -m simpy_demo
# or
poetry run python src/simpy_demo/scenarios.py
```

## Architecture

### Module Structure

```
src/simpy_demo/
├── __init__.py      # Public API exports
├── __main__.py      # Entry point for `python -m simpy_demo`
├── models.py        # Pydantic schemas (MachineConfig, ScenarioConfig, Product, MaterialType)
├── equipment.py     # SmartEquipment class (core machine simulation logic)
├── simulation.py    # ProductionLine class (factory orchestration)
└── scenarios.py     # Runtime control, scenario definitions, results reporting
```

### Core Simulation Pattern
The system uses SimPy's cooperative multitasking with generator-based coroutines:
- **`simpy.Environment`**: Priority queue scheduler that advances time only on events
- **`SmartEquipment`**: Python generators (`yield`) representing machines
- **`simpy.Store`**: Buffers for inter-machine synchronization; `yield store.get()` models starvation, `yield store.put()` models blocking

### Key Classes

- **`models.py`**:
  - `MachineConfig` (Pydantic): Equipment parameters (UPH, MTBF, jam probability, defect rate, buffer capacity)
  - `ScenarioConfig` (Pydantic): Experiment definition with layout of machines
  - `Product` (Pydantic): Composite material pattern for traceability (Tube → Case → Pallet)
  - `MaterialType` (Enum): TUBE, CASE, PALLET, NONE

- **`equipment.py`**:
  - `SmartEquipment`: Machine process with 6-phase cycle: COLLECT → BREAKDOWN CHECK → MICROSTOP CHECK → EXECUTE → TRANSFORM → INSPECT/ROUTE

- **`simulation.py`**:
  - `ProductionLine`: Factory floor orchestrator; builds layout, runs simulation, compiles results

- **`scenarios.py`**:
  - `get_default_scenario()`: Returns the default cosmetics line scenario
  - `run_simulation()`: Runs a scenario and prints OEE analysis

### OEE Loss Mapping
- **Availability**: `mtbf_min`/`mttr_min` (time-based failures)
- **Performance**: `jam_prob`/`jam_time_sec` (cycle-based microstops)
- **Quality**: `defect_rate`/`detection_prob` (scrap routing)

### Data Outputs
- **Telemetry (`df_ts`)**: Time-series snapshots (buffer levels, machine states) at 1-second intervals
- **Event Log (`df_ev`)**: State transition log for OEE calculation and process mining

## Configuration

Modify scenarios in `scenarios.py` or create custom `ScenarioConfig` instances:
- Change `buffer_capacity` to test accumulation effects
- Adjust `mtbf_min` to test reliability impact
- Modify `uph` to break V-Curve balancing
