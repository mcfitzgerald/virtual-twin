# Changelog

See the full changelog in the repository root:

**[CHANGELOG.md](https://github.com/michael/simpy-demo/blob/main/CHANGELOG.md)**

## Recent Versions

### [0.10.0] - 2025-11-29

**Integration test suite with manufacturing reality checks**

- 37 tests across 6 test files
- Manufacturing reality validation (OEE bounds, throughput limits, economics)
- Optimization experiment validation (loss attribution, bottleneck identification)
- pytest and pytest-timeout dev dependencies

### [0.9.1] - 2025-11-29

**MkDocs documentation site**

- Full documentation site with Material theme
- Getting started, user guide, tutorials, and reference sections

### [0.9.0] - 2025-11-29

**CLI subcommands and scenario bundles**

- Added `configure` and `simulate` CLI subcommands
- Scenario bundles for auditable, reproducible runs
- Codegen module for scenario generation
- Runtime module for executing scenario bundles

### [0.8.0] - 2025-11-26

**Configurable equipment phases**

- BehaviorOrchestrator for pluggable phase system
- Individual phase handlers (Collect, Breakdown, Microstop, Execute, Transform, Inspect)
- YAML-defined behavior configuration

### [0.7.0] - 2025-11-26

**Graph-based topology**

- TopologyGraph for DAG-based production lines
- LayoutBuilder for graph layout construction
- Support for branching, merging, and conditional routing

### [0.4.0] - 2025-11-25

**Economic tracking**

- Product/SKU configuration
- Cost rates for equipment
- Material cost, conversion cost, revenue, gross margin tracking

### [0.3.0] - 2025-11-25

**YAML configuration system**

- Layered configuration: runs, scenarios, topologies, equipment
- ConfigLoader with name-based resolution
- CLI with --run, --config, --export options

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| 0.10.0 | 2025-11-29 | Integration test suite, manufacturing reality checks |
| 0.9.1 | 2025-11-29 | MkDocs documentation site |
| 0.9.0 | 2025-11-29 | CLI subcommands, scenario bundles |
| 0.8.2 | 2025-11-29 | Simplified telemetry |
| 0.8.1 | 2025-11-26 | Removed backward compatibility |
| 0.8.0 | 2025-11-26 | BehaviorOrchestrator, phases |
| 0.7.0 | 2025-11-26 | Graph topology |
| 0.6.0 | 2025-11-26 | Expression engine (later removed) |
| 0.5.0 | 2025-11-26 | Defaults/constants config |
| 0.4.2 | 2025-11-26 | Semgrep hardcode rules |
| 0.4.1 | 2025-11-25 | Incremental telemetry |
| 0.4.0 | 2025-11-25 | Products and economics |
| 0.3.1 | 2025-11-25 | Configurable start_time |
| 0.3.0 | 2025-11-25 | YAML configuration |
| 0.2.1 | 2025-11-25 | Telemetry interval |
| 0.2.0 | 2025-11-25 | SimulationEngine |
| 0.1.0 | 2025-11-24 | Initial release |
