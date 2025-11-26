# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.1] - 2025-11-25

### Changed
- Telemetry now shows **incremental** values per interval (not cumulative)
  - Production counts, defects, and economic values are deltas for each 5-min interval
  - Buffer levels and machine states remain as current values
- CLI summary now sums incremental values for totals

## [0.4.0] - 2025-11-25

### Added
- **Product/SKU configuration** (`config/products/*.yaml`)
  - Product definitions with name, description, physical attributes
  - Economic attributes: `material_cost` and `selling_price` per pallet
- **Cost rates for equipment** (`cost_rates` in equipment YAML)
  - `labor_per_hour`, `energy_per_hour`, `overhead_per_hour`
  - Conversion cost computed from wall-clock simulation time
- **Production counters by material type**
  - `tubes_produced`, `cases_produced`, `pallets_produced`
  - `defects_created`, `defects_detected`, `defects_escaped`
- **Economic data in telemetry** (5-minute intervals)
  - SKU context: `sku_name`, `sku_description`, `size_oz`, `units_per_case`, `cases_per_pallet`
  - Costs: `material_cost`, `conversion_cost`, `revenue`, `gross_margin`
- **Economic summary in CLI output**
  - Production counts, revenue, costs, margin percentage, cost per pallet
- `ProductConfig` and `CostRates` Pydantic models
- `product` field in `RunConfig` to reference product configuration

### Changed
- `Equipment` now tracks time spent in each state for conversion cost
- `_transform_material()` returns tuple of (product, new_defect_created)
- Telemetry interval updated to 300 seconds (5 minutes) by default
- `loader.py` loads products and equipment cost_rates
- `MachineConfig` includes `cost_rates` field

## [0.3.1] - 2025-11-25

### Added
- `start_time` field in RunConfig for configurable simulation timestamps
- ISO 8601 format support (e.g., `"2025-01-06T06:00:00"`)
- Timestamps now embedded during simulation (not post-hoc)

### Changed
- `engine.py` now computes `datetime = start_time + timedelta(seconds=env.now)` during monitoring
- Export filenames use configured start_time instead of current time
- Removed post-hoc datetime conversion from `run.py`

## [0.3.0] - 2025-11-25

### Added
- YAML-based layered configuration system
- `config/` directory with hierarchical structure:
  - `runs/` - Run configurations (duration, seed, telemetry interval)
  - `scenarios/` - Scenario definitions (topology + equipment references)
  - `topologies/` - Line structure definitions (station order, batch sizes)
  - `equipment/` - Equipment parameter files
  - `materials/` - Material type definitions
- `loader.py` - YAML loader with name-based resolution
- CLI arguments: `--run`, `--config`, `--export`, `--output`
- `ConfigLoader` class for programmatic config loading

### Changed
- `SimulationEngine` now loads from YAML configs instead of Python objects
- `run_simulation()` accepts run name and config directory path
- Configuration schemas moved to dataclasses in `loader.py`
- `config.py` now re-exports from `loader.py` for convenience

### Removed
- `baseline.py` - Replaced by `config/equipment/*.yaml`
- `topology.py` - Replaced by `config/topologies/*.yaml`
- Old Pydantic-based `EquipmentParams` and `ScenarioConfig`

## [0.2.1] - 2025-11-25

### Added
- `telemetry_interval_sec` parameter in `ScenarioConfig` (default: 300 seconds / 5 minutes)
- Configurable telemetry collection interval for managing dataset size in long simulations

## [0.2.0] - 2025-11-25

### Added
- `topology.py` - Line structure definitions (`Station`, `CosmeticsLine`)
- `config.py` - Scenario configuration schemas (`EquipmentParams`, `ScenarioConfig`)
- `baseline.py` - Default parameter values for cosmetics line equipment
- `engine.py` - `SimulationEngine` class for running simulations
- `run.py` - Entry point with OEE reporting
- Grouped parameter models: `ReliabilityParams`, `PerformanceParams`, `QualityParams`

### Changed
- Refactored architecture to separate Topology, Baseline, and Scenarios
- Renamed `SmartEquipment` to `Equipment` in `equipment.py`
- Updated `MachineConfig` to use grouped parameter sub-models
- Config access now uses grouped paths (e.g., `cfg.reliability.mtbf_min` instead of `cfg.mtbf_min`)
- Updated `__init__.py` exports for new public API
- Updated documentation in `CLAUDE.md` and `README.md`

### Removed
- `scenarios.py` - Replaced by `run.py`, `config.py`, and `baseline.py`
- `simulation.py` - Replaced by `engine.py`
- `Depalletizer` station - Infinite source now handled by engine

## [0.1.0] - 2025-11-24

### Added
- Initial implementation of SimPy production line simulator
- `SmartEquipment` class with 6-phase cycle
- `ProductionLine` class for factory orchestration
- Pydantic models for configuration and products
- OEE analysis and telemetry output
