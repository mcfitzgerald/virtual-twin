# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
