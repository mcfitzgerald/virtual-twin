# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.0] - 2025-11-29

### Added
- **CLI subcommands** for `configure` and `simulate` workflow (Phase 5 of refac3.md)
  - `python -m simpy_demo configure --run <name>` - Generate scenario bundle from config
  - `python -m simpy_demo simulate --scenario <path>` - Run a scenario bundle
  - `python -m simpy_demo run --run <name>` - Direct run (combines configure + simulate)
- **Scenario bundles** (`scenarios/`) for auditable, reproducible runs
  - `scenario.py` - Lightweight runner script
  - `config_snapshot.yaml` - Frozen resolved configuration
  - `metadata.json` - Generation metadata (git commit, hash, timestamp, version)
  - `output/` - Simulation results (telemetry.csv, events.csv, summary.json)
- **Codegen module** (`src/simpy_demo/codegen/`)
  - `ScenarioGenerator` class for generating scenario bundles
  - Jinja2 template for `scenario.py` generation
  - SHA256 config hashing for reproducibility verification
- **Runtime module** (`src/simpy_demo/simulation/runtime.py`)
  - `execute_scenario()` function for running from config snapshots
- **Dry-run mode**: `python -m simpy_demo configure --run <name> --dry-run`
- **New dependencies**: `jinja2>=3.1.6`
- New exports in `__init__.py`: `ScenarioGenerator`, `configure`, `simulate`, `execute_scenario`

### Changed
- CLI now supports subcommands: `run`, `configure`, `simulate`
- Legacy mode preserved: `python -m simpy_demo --run <name>` still works
- `run.py` refactored with subcommand architecture
- `simulate` command exports to bundle's `output/` directory by default
- Summary JSON includes production counts, economics, and OEE by machine

### Technical Notes
- Scenario bundles enable comparison between runs (diff config_snapshot.yaml)
- Config hash ensures configuration hasn't changed between configure and simulate
- Git commit and dirty status captured in metadata for version tracking
- Generated scenario.py files are executable (`chmod +x`)

## [0.8.2] - 2025-11-29

### Added
- `net_weight_g` field to `ProductConfig` for product-level weight attribute

### Removed
- **Expression Engine** (`src/simpy_demo/expressions/`) - ~230 lines deleted
  - Over-engineered for prototype needs
  - Safe AST-based expression evaluation no longer needed
- **Telemetry Generator** (`src/simpy_demo/factories/telemetry.py`) - ~150 lines deleted
  - Generator types (gaussian, fixed, expression, count_inputs) removed
  - Per-item telemetry generation deferred to future enhancement
- **Materials Configuration** (`config/materials/cosmetics.yaml`) - ~40 lines deleted
  - Telemetry generator configs no longer used
- `MaterialsConfig` dataclass from loader.py
- `materials` field from `TopologyConfig` and `ResolvedConfig`
- `telemetry_gen` parameter from `Equipment`, `LayoutBuilder`, and `SimulationEngine`
- Exports removed from `__init__.py`: `ExpressionEngine`, `TelemetryGenerator`, `MaterialsConfig`

### Changed
- `TransformPhase.execute()` simplified - no longer uses TelemetryGenerator
- Product telemetry now empty dict (simplified for prototype)
- `Equipment` constructor no longer accepts `telemetry_gen` parameter
- `LayoutBuilder` constructor no longer accepts `telemetry_gen` parameter
- `SimulationEngine._build_layout()` and `_build_graph_layout()` simplified

### Technical Notes
- ~420 lines of code deleted total
- Telemetry simplified to product-level attributes (size_oz, net_weight_g)
- No functional changes to simulation output (production counts, OEE, economics unchanged)
- Per-item telemetry generation deferred to Future Enhancements

## [0.8.1] - 2025-11-26

### Changed
- **Deprecated inline behavior implementation** (Phase 4 Addendum of refac3.md)
  - Removed `Equipment._run_inline()` method (~76 lines) - behavior now always uses orchestrator
  - Removed `Equipment._transform_material()` method (~39 lines) - logic in TransformPhase
  - Inlined `Equipment._run_with_orchestrator()` contents directly into `run()`
  - Equipment always creates orchestrator from `DEFAULT_BEHAVIOR` if none provided
  - `SimulationEngine` always creates `BehaviorOrchestrator` using `DEFAULT_BEHAVIOR` as fallback
  - `LayoutBuilder` always creates orchestrator from `DEFAULT_BEHAVIOR` if none provided

### Removed
- `Equipment._run_inline()` method (backward compatibility code)
- `Equipment._transform_material()` method (duplicated in TransformPhase)
- Conditional orchestrator creation in `SimulationEngine.run_resolved()`

### Technical Notes
- Equipment.py reduced from ~330 lines to ~198 lines
- Single code path through behavior system (no more conditional orchestrator check)
- Identical simulation results verified (no functional changes)
- All code paths now use `BehaviorOrchestrator` with `DEFAULT_BEHAVIOR` fallback

## [0.8.0] - 2025-11-26

### Added
- **Configurable equipment phases** (`src/simpy_demo/behavior/`) - YAML-defined behavior (Phase 4 of refac3.md)
  - `Phase` abstract base class with execute/is_enabled interface
  - `PhaseConfig` and `PhaseContext` dataclasses for phase coordination
  - `PhaseResult` for capturing phase outcomes
- **Individual phase handlers** (`src/simpy_demo/behavior/phases/`):
  - `CollectPhase`: Wait for and gather inputs from upstream
  - `BreakdownPhase`: Poisson-based failure check (availability loss)
  - `MicrostopPhase`: Bernoulli per-cycle jam check (performance loss)
  - `ExecutePhase`: Value-add processing time
  - `TransformPhase`: Convert inputs to output with telemetry generation
  - `InspectPhase`: Quality inspection and conditional routing
- **BehaviorOrchestrator** (`src/simpy_demo/behavior/orchestrator.py`):
  - Coordinates phase execution based on behavior config
  - Checks enabled conditions for each phase
  - Passes shared context between phases
  - `DEFAULT_BEHAVIOR` singleton for default 6-phase cycle
- **Behavior YAML config** (`config/behaviors/default_6phase.yaml`):
  - Declarative definition of equipment phases
  - Handler class references
  - Enabled condition expressions
- **Config loader support**:
  - `load_behavior()` method in ConfigLoader
  - `behavior` field in ScenarioConfig (optional reference)
  - `behavior` field in ResolvedConfig
- New exports in `__init__.py`: `BehaviorConfig`, `BehaviorOrchestrator`, `DEFAULT_BEHAVIOR`, `Phase`, `PhaseConfig`, `PhaseContext`, `PhaseResult`, `CollectPhase`, `BreakdownPhase`, `MicrostopPhase`, `ExecutePhase`, `TransformPhase`, `InspectPhase`

### Changed
- `Equipment` now accepts optional `orchestrator` parameter for YAML-defined phases
- `Equipment.run()` delegates to `_run_with_orchestrator()` when orchestrator provided
- Original inline 6-phase cycle preserved in `_run_inline()` for backward compatibility
- `SimulationEngine` now creates `BehaviorOrchestrator` from resolved config and passes to Equipment
- `LayoutBuilder` accepts and passes orchestrator for graph-based topologies
- Default behavior config (`config/behaviors/default_6phase.yaml`) is loaded automatically when present

### Technical Notes
- Orchestrator is used by default when `config/behaviors/default_6phase.yaml` exists
- Inline implementation is fallback when no behavior config is available
- Phase handlers are registered in `PHASE_REGISTRY` for lookup by name
- PhaseContext provides shared state between phases (upstream/downstream stores, telemetry_gen, log callback)
- Each phase is a generator yielding SimPy events and returning PhaseResult
- Proper SimPy yield/send protocol ensures values flow correctly between phases
- Enabled conditions are evaluated by phase's `is_enabled()` method based on MachineConfig

## [0.7.0] - 2025-11-26

### Added
- **Graph-based topology** (`src/simpy_demo/topology/`) for DAG-based production lines (Phase 3 of refac3.md)
  - `TopologyGraph` class with nodes, edges, cycle detection, and topological ordering
  - `StationNode` dataclass for representing stations in the graph
  - `BufferEdge` dataclass for connections with optional conditions
  - Special nodes: `_source`, `_sink`, `_reject` for standard flow endpoints
  - `from_linear()` class method for backward-compatible conversion
- **Graph-aware layout builder** (`src/simpy_demo/simulation/layout.py`)
  - `LayoutBuilder` class for constructing SimPy layout from `TopologyGraph`
  - `NodeConnections` for multi-path upstream/downstream routing
  - `RoutingRule` for conditional routing (e.g., quality gates)
  - Supports branching (one-to-many), merging (many-to-one), and conditional routing
- **New topology config format** with explicit nodes and edges:
  - `config/topologies/cosmetics_line_graph.yaml` - Graph-based example with quality gate routing
  - `config/scenarios/baseline_graph.yaml` - Scenario using graph topology
  - `config/runs/baseline_graph_8hr.yaml` - Run config for graph topology
- New dataclasses in `loader.py`:
  - `NodeConfig` - Node configuration for graph topology
  - `EdgeConfig` - Edge configuration with conditions
- New exports in `__init__.py`: `TopologyGraph`, `StationNode`, `BufferEdge`, `CycleDetectedError`, `NodeConfig`, `EdgeConfig`

### Changed
- `TopologyConfig` now supports both linear (`stations` list) and graph (`nodes`/`edges` lists) formats
- `TopologyConfig.to_graph()` method converts either format to `TopologyGraph`
- `TopologyConfig.is_graph_topology` property to detect format
- `ConfigLoader.load_topology()` parses both formats from YAML
- `ConfigLoader.build_machine_configs()` supports graph topology (iterates in topological order)
- `Equipment` accepts optional `connections` parameter for graph-based routing
- `Equipment.run()` Phase 6 uses `NodeConnections.get_route()` for conditional routing
- `SimulationEngine.run_resolved()` uses `_build_graph_layout()` for graph topologies
- Added `_build_graph_layout()` method to `SimulationEngine`

### Technical Notes
- Graph topology is fully backward compatible - existing linear configs continue to work
- Graph format enables: branching, merging, conditional routing (quality gates), rework loops
- Cycle detection via Kahn's algorithm in `TopologyGraph.topological_order()`
- Condition expressions support: `product.is_defective`, `not product.is_defective`

## [0.6.0] - 2025-11-26

### Added
- **Expression Engine** (`src/simpy_demo/expressions/`) for evaluating YAML config expressions
  - Safe AST-based evaluation (no `eval()`) for security
  - `${CONSTANT_NAME}` substitution from `constants.yaml`
  - Arithmetic operators: `+`, `-`, `*`, `/`
  - Aggregate functions: `sum(inputs, 'field')`, `len(inputs)`, `max(inputs, 'field')`, `min(inputs, 'field')`
- **Telemetry Generator** (`src/simpy_demo/factories/telemetry.py`) for config-driven telemetry
  - Generator types: `gaussian`, `fixed`, `expression`, `count_inputs`
  - Replaces hardcoded telemetry values in `equipment.py`
- Enhanced materials config (`config/materials/cosmetics.yaml`) with telemetry generators:
  - TUBE: `fill_level` (gaussian), `weight` (fixed)
  - CASE: `weight` (expression), `tube_count` (count_inputs)
  - PALLET: `location` (fixed), `weight` (expression), `case_count` (count_inputs)
- `materials` field in `TopologyConfig` to reference materials config
- `materials` field in `ResolvedConfig` for fully resolved config
- New exports in `__init__.py`: `ExpressionEngine`, `TelemetryGenerator`, `MaterialsConfig`

### Changed
- `Equipment` now accepts optional `TelemetryGenerator` for config-driven telemetry
- `_transform_material()` uses `TelemetryGenerator` instead of hardcoded if/elif
- `SimulationEngine._build_layout()` creates and passes `TelemetryGenerator` to equipment
- Telemetry values now configurable in YAML instead of code:
  - `random.gauss(100, 1.0)` → `generator: gaussian` with `${NOMINAL_FILL_LEVEL_ML}`
  - `sum([100 for _]) + 50` → `generator: expression` with `sum(inputs, 'telemetry.weight') + ${CASE_TARE_WEIGHT_G}`
  - `"Warehouse_A"` → `generator: fixed` with `${DEFAULT_WAREHOUSE}`

### Technical Notes
- Expression engine uses Python's `ast` module for safe parsing
- Telemetry config supports nested field access (e.g., `telemetry.weight`)
- Backward compatible: equipment without telemetry_gen produces empty telemetry

## [0.5.0] - 2025-11-26

### Added
- **Config foundation** for extracting hardcoded values (Phase 1 of refac3.md)
- `config/defaults.yaml` - Global default values for simulation, equipment, products, and sources
- `config/constants.yaml` - Named constants (TUBE_WEIGHT_G, SECONDS_PER_HOUR, DEFAULT_WAREHOUSE, etc.)
- `config/sources/infinite_raw.yaml` - Configurable source for raw material input
- New dataclasses in `loader.py`:
  - `DefaultsConfig` - Global defaults container
  - `ConstantsConfig` - Named constants container with `get()` method
  - `SourceConfig` - Source configuration (initial_inventory, material_type, parent_machine)
- New loader methods: `load_defaults()`, `load_constants()`, `load_source()`
- `source` field in `TopologyConfig` to reference source configs
- `source` and `constants` fields in `ResolvedConfig`
- `source` parameter in `SimulationEngine.run_config()` for programmatic use

### Changed
- `ConfigLoader` now loads defaults and constants on initialization
- All loader methods use `defaults.yaml` values instead of inline hardcoded defaults
- `engine.py` uses `SourceConfig` for initial_inventory (was hardcoded 100000) and parent_machine (was "Raw")
- `equipment.py` uses `math.exp()` instead of hardcoded Euler approximation (2.718)
- `TopologyConfig` now includes `source` reference (default: "infinite_raw")
- Topology YAML files can specify `source: <name>` to reference source configs

### Technical Notes
- Remaining telemetry hardcodes (gauss params, weights, locations) will be addressed in Phase 2
- Time conversion constants (60, 3600) kept as code constants since they're physics, not config

## [0.4.2] - 2025-11-26

### Added
- **Semgrep hardcode detection rules** (`.semgrep/rules/hardcoded-values.yaml`)
  - `simpy-numeric-field-default`: Detects hardcoded defaults in Pydantic/dataclass fields
  - `simpy-numeric-dict-get-default`: Detects hardcoded dict.get() defaults
  - `simpy-numeric-literal-in-expression`: Detects magic numbers in expressions
  - `simpy-magic-3600`: Detects seconds-per-hour magic number
  - `simpy-magic-60`: Detects seconds-per-minute magic number
  - `simpy-hardcoded-gaussian-telemetry`: Detects hardcoded gaussian parameters
  - `simpy-hardcoded-location-string`: Detects hardcoded warehouse locations
  - `simpy-hardcoded-equipment-name-string`: Detects hardcoded equipment names
  - `simpy-hardcoded-large-range`: Detects large hardcoded ranges (>100)
  - `simpy-hardcoded-euler`: Detects hardcoded Euler's number approximation
  - `simpy-hardcoded-list-comprehension`: Detects hardcoded values in list comprehensions
- Baseline scan identifying 48 hardcoded values to extract to config:
  - 15 field defaults (Pydantic/dataclass)
  - 11 numeric literals in expressions
  - 9 dict.get() defaults
  - 5 magic number 3600 (seconds per hour)
  - 2 magic number 60 (seconds per minute)
  - 1 hardcoded range(100000)
  - 1 hardcoded "Raw" equipment name
  - 1 hardcoded Euler's number approximation
  - 1 hardcoded gaussian parameters
  - 1 hardcoded list comprehension value
  - 1 hardcoded warehouse location

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
