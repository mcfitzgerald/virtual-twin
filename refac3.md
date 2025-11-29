# SimPy-Demo Refactoring Plan v3

> **Purpose**: Persistent planning document for major architectural refactoring
> **Status**: Planning phase
> **Last Updated**: 2025-01-26

---

## Vision (from SPEC.md)

```
Flow: configure → simulate → output
```

1. **Configure**: Edit YAML configs → run `configure` → generates standalone `scenario` Python file
2. **Simulate**: Run `simulate` on a scenario → generates telemetry + events CSVs
3. **Bundle**: Config + scenario files are bundled together for auditing/comparison

### Core Principles
- **Composability**: Multiple lines, campaign of SKUs strung together
- **Extensibility**: Add new equipment/behaviors without code changes
- **Configurability**: ALL behavior defined in YAML, code is generic

---

## Current State Analysis

### What Works
- YAML config system (runs/, scenarios/, topologies/, equipment/, products/)
- SimPy integration with Equipment class
- Telemetry and event logging
- OEE and economics calculations

### What's Broken

#### Hardcoded Values (Semgrep will detect these)
| File | Line | Hardcode | Should Be |
|------|------|----------|-----------|
| `equipment.py` | 187 | `gauss(100, 1.0)` | materials.yaml telemetry config |
| `equipment.py` | 199 | `sum([100 for _]) + 50` | expression in materials.yaml |
| `equipment.py` | 211 | `"Warehouse_A"` | constants.yaml |
| `engine.py` | 122 | `100000` | sources.yaml |
| `engine.py` | 127 | `"Raw"` | sources.yaml |
| `models.py` | 38 | `mttr_min=60.0` | defaults.yaml |
| `models.py` | 45 | `jam_time_sec=10.0` | defaults.yaml |
| `models.py` | 58-60 | `labor=25, energy=5, overhead=10` | defaults.yaml |
| `models.py` | 91 | `buffer_capacity=50` | defaults.yaml |

#### Architecture Issues
1. **No `configure` command** - Can't generate standalone scenarios
2. **No scenario bundling** - No auditing/versioning of runs
3. **Single line only** - No multi-line or campaign support
4. **Inline product creation** - `equipment._transform_material()` has if/elif
5. **Monolithic engine** - Mixes orchestration with implementation
6. **Linear topology** - No graph for branching/merging
7. **Hardcoded 6-phase cycle** - Can't add/reorder phases
8. **materials.yaml unused** - Defined but never loaded

---

## Revised Architecture

### New CLI Commands

```bash
# Configure: Generate a standalone scenario from YAML configs
simpy-demo configure --run baseline_8hr --output scenarios/

# Simulate: Run a scenario, generate output
simpy-demo simulate --scenario scenarios/baseline_8hr_20250126_143022.py --export

# Or combined (current behavior, for convenience)
simpy-demo run --run baseline_8hr --export
```

### Scenario File Structure

A generated scenario is a **lightweight Python file** that references external config:

```python
#!/usr/bin/env python3
"""
Scenario: baseline_8hr
Generated: 2025-01-26T14:30:22
Config Hash: abc123
Bundle: scenarios/baseline_8hr_20250126_143022/
"""

from pathlib import Path
from simpy_demo.simulation.runtime import execute_scenario

SCENARIO_DIR = Path(__file__).parent
CONFIG_PATH = SCENARIO_DIR / "config_snapshot.yaml"

if __name__ == "__main__":
    execute_scenario(CONFIG_PATH)
```

**Design Decision**: Reference YAML instead of embedding dict
- Smaller scenario.py files
- Easier to diff configs between runs
- Config is human-readable in the bundle
- Requires config_snapshot.yaml to exist (enforced by bundle structure)

### Scenario Bundling

```
scenarios/
├── baseline_8hr_20250126_143022/
│   ├── scenario.py           # Lightweight runner (references config)
│   ├── config_snapshot.yaml  # Frozen resolved config at generation time
│   ├── metadata.json         # Hash, timestamp, git commit, CLI args, etc.
│   └── output/               # Created after simulation
│       ├── telemetry.csv
│       ├── events.csv
│       └── summary.json      # OEE, economics summary
```

### Metadata Schema

**`metadata.json`**:
```json
{
  "scenario_name": "baseline_8hr",
  "generated_at": "2025-01-26T14:30:22Z",
  "config_hash": "sha256:abc123...",
  "git_commit": "2aa9130",
  "git_dirty": false,
  "cli_command": "simpy-demo configure --run baseline_8hr",
  "simpy_demo_version": "0.9.0",
  "python_version": "3.11.5",
  "source_configs": {
    "run": "config/runs/baseline_8hr.yaml",
    "scenario": "config/scenarios/baseline.yaml",
    "topology": "config/topologies/cosmetics_line.yaml",
    "equipment": ["config/equipment/filler.yaml", "..."],
    "product": "config/products/fresh_toothpaste_5oz.yaml"
  }
}

---

## Target Directory Structure

```
simpy-demo/
├── .semgrep/                     # Hardcode detection rules
│   ├── rules/
│   │   ├── hardcoded-values.yaml
│   │   ├── magic-numbers.yaml
│   │   └── config-strings.yaml
│   └── tests/
│
├── config/                       # YAML configuration (source of truth)
│   ├── defaults.yaml             # Global defaults
│   ├── constants.yaml            # Named constants for expressions
│   ├── runs/*.yaml               # Run parameters
│   ├── scenarios/*.yaml          # Scenario definitions
│   ├── topologies/*.yaml         # Graph topology (nodes + edges)
│   ├── equipment/*.yaml          # Equipment parameters
│   ├── products/*.yaml           # SKU definitions
│   ├── materials/*.yaml          # Material telemetry specs
│   ├── sources/*.yaml            # Source configurations
│   ├── behaviors/*.yaml          # Equipment phase behaviors
│   └── campaigns/*.yaml          # Multi-run campaign definitions (NEW)
│
├── scenarios/                    # Generated scenario bundles (NEW)
│   └── {name}_{timestamp}/
│       ├── scenario.py
│       ├── config_snapshot.yaml
│       └── metadata.json
│
├── src/simpy_demo/
│   ├── __init__.py
│   ├── __main__.py               # CLI entry (configure/simulate/run)
│   │
│   ├── cli/                      # CLI commands (NEW)
│   │   ├── __init__.py
│   │   ├── configure.py          # configure command
│   │   ├── simulate.py           # simulate command
│   │   └── run.py                # run command (combined)
│   │
│   ├── config/                   # Configuration loading (refactored)
│   │   ├── __init__.py
│   │   ├── loader.py             # YAML loading
│   │   ├── resolver.py           # Config resolution & inheritance
│   │   ├── validator.py          # Schema validation
│   │   └── schemas.py            # Pydantic schemas
│   │
│   ├── codegen/                  # Scenario generation (NEW)
│   │   ├── __init__.py
│   │   ├── generator.py          # Generate scenario.py files
│   │   └── templates/            # Jinja2 templates for scenarios
│   │
│   ├── expressions/              # Expression engine (NEW)
│   │   ├── __init__.py
│   │   ├── engine.py             # Evaluate ${CONST} and sum(inputs, 'field')
│   │   └── functions.py          # Built-in functions (sum, len, max, min)
│   │
│   ├── topology/                 # Graph topology (NEW)
│   │   ├── __init__.py
│   │   ├── graph.py              # TopologyGraph class
│   │   ├── node.py               # StationNode
│   │   └── edge.py               # BufferEdge with conditions
│   │
│   ├── simulation/               # Simulation runtime
│   │   ├── __init__.py
│   │   ├── runtime.py            # execute_scenario() entry point
│   │   ├── equipment.py          # Equipment class (simplified)
│   │   ├── layout.py             # Build SimPy layout from graph
│   │   ├── monitoring.py         # TelemetryCollector
│   │   └── results.py            # ResultsCompiler
│   │
│   ├── behavior/                 # Configurable equipment behavior (NEW)
│   │   ├── __init__.py
│   │   ├── orchestrator.py       # Phase orchestration
│   │   └── phases/               # Individual phase handlers
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── collect.py
│   │       ├── breakdown.py
│   │       ├── microstop.py
│   │       ├── execute.py
│   │       ├── transform.py
│   │       └── inspect.py
│   │
│   ├── factories/                # Entity factories (NEW)
│   │   ├── __init__.py
│   │   ├── product.py            # ProductFactory
│   │   └── telemetry.py          # TelemetryGenerator
│   │
│   └── models.py                 # Domain models (cleaned up)
│
└── output/                       # Default output directory
```

---

## Implementation Phases

### Phase 0: Semgrep Hardcode Detection (v0.4.2)

**Goal**: Establish guardrails before refactoring

#### 0.1 Create Semgrep Rules

**New file**: `.semgrep/rules/hardcoded-values.yaml`
```yaml
rules:
  - id: simpy-hardcoded-range
    pattern: range($NUM)
    message: "Hardcoded range - use config.source.initial_inventory"
    languages: [python]
    severity: WARNING
    paths:
      include:
        - src/simpy_demo/

  - id: simpy-hardcoded-gaussian
    patterns:
      - pattern: random.gauss($MEAN, $STD)
      - metavariable-comparison:
          metavariable: $MEAN
          comparison: $MEAN > 1
    message: "Hardcoded telemetry params - use materials.yaml"
    languages: [python]
    severity: WARNING

  - id: simpy-hardcoded-location-string
    pattern-regex: '"Warehouse_\w+"'
    message: "Hardcoded location - use constants.yaml"
    languages: [python]
    severity: WARNING

  - id: simpy-magic-time-conversion
    patterns:
      - pattern-either:
          - pattern: $X * 3600
          - pattern: $X / 3600
          - pattern: $X * 60
          - pattern: $X / 60
    message: "Magic number in time conversion - use SECONDS_PER_HOUR constant"
    languages: [python]
    severity: INFO
```

#### 0.2 Pre-commit Integration

**New file**: `.pre-commit-config.yaml` (or update existing)
```yaml
repos:
  - repo: https://github.com/semgrep/pre-commit
    rev: 'v1.52.0'
    hooks:
      - id: semgrep
        args: ['--config', '.semgrep/rules/', '--error']
```

#### 0.3 Run Baseline Scan
```bash
semgrep --config .semgrep/rules/ src/simpy_demo/ --json > hardcode_baseline.json
```

---

### Phase 1: Config Foundation (v0.5.0)

**Goal**: Extract all hardcodes to YAML, establish defaults/constants

#### 1.1 New Config Files

**`config/defaults.yaml`**
```yaml
version: "1.0"

time:
  seconds_per_minute: 60
  seconds_per_hour: 3600

simulation:
  telemetry_interval_sec: 300.0
  random_seed: 42
  duration_hours: 8.0

equipment:
  buffer_capacity: 50
  reliability:
    mtbf_min: null
    mttr_min: 60.0
  performance:
    jam_prob: 0.0
    jam_time_sec: 10.0
  quality:
    defect_rate: 0.0
    detection_prob: 0.0
  cost_rates:
    labor_per_hour: 25.0
    energy_per_hour: 5.0
    overhead_per_hour: 10.0

source:
  initial_inventory: 100000
  material_type: "None"
  parent_machine: "Raw"
```

**`config/constants.yaml`**
```yaml
constants:
  # Physical constants
  TUBE_WEIGHT_G: 100
  CASE_TARE_WEIGHT_G: 50
  PALLET_TARE_WEIGHT_KG: 25

  # Telemetry defaults
  NOMINAL_FILL_LEVEL_ML: 100
  FILL_STDDEV_ML: 1.0

  # Locations
  DEFAULT_WAREHOUSE: "Warehouse_A"
  REJECT_BIN: "Reject_Bin"

  # Time (for reference, also in defaults.yaml)
  SECONDS_PER_HOUR: 3600
  SECONDS_PER_MINUTE: 60
```

**`config/sources/infinite_raw.yaml`**
```yaml
name: infinite_raw
initial_inventory: 100000
material_type: "None"
parent_machine: "Raw"
```

#### 1.2 Update Loader

- Add `load_defaults()`, `load_constants()`, `load_source()` methods
- Add `DefaultsConfig`, `ConstantsConfig`, `SourceConfig` dataclasses
- Wire into `ResolvedConfig`

#### 1.3 Update Engine

- Replace hardcoded `100000` with `source_config.initial_inventory`
- Replace `"Raw"` with `source_config.parent_machine`

#### 1.4 Verification
```bash
# Before
semgrep --config .semgrep/rules/ src/simpy_demo/ --json | jq '.results | length'
# After (should be fewer)
```

---

### Phase 2: Expression Engine & Telemetry (v0.6.0)

**Goal**: Config-driven telemetry generation with expression support

#### 2.1 Expression Engine

**New file**: `src/simpy_demo/expressions/engine.py`
```python
class ExpressionEngine:
    """Evaluate YAML expressions with constants and aggregations."""

    FUNCTIONS = {
        "sum": lambda inputs, field: sum(getattr(i, field, 0) for i in inputs),
        "len": lambda inputs: len(inputs),
        "max": lambda inputs, field: max(getattr(i, field, 0) for i in inputs),
        "min": lambda inputs, field: min(getattr(i, field, 0) for i in inputs),
    }

    def __init__(self, constants: dict):
        self.constants = constants

    def evaluate(self, expr: str, context: dict) -> Any:
        """
        Evaluate expression with context.

        Supports:
        - ${CONSTANT_NAME} substitution
        - sum(inputs, 'field'), len(inputs), max/min
        - Arithmetic: +, -, *, /
        """
```

#### 2.2 Enhanced Materials Config

**`config/materials/cosmetics.yaml`**
```yaml
name: cosmetics

types:
  TUBE:
    telemetry:
      fill_level:
        generator: gaussian
        mean: "${NOMINAL_FILL_LEVEL_ML}"
        stddev: "${FILL_STDDEV_ML}"
      weight:
        generator: fixed
        value: "${TUBE_WEIGHT_G}"

  CASE:
    telemetry:
      weight:
        generator: expression
        expr: "sum(inputs, 'telemetry.weight') + ${CASE_TARE_WEIGHT_G}"
      tube_count:
        generator: count_inputs

  PALLET:
    telemetry:
      location:
        generator: fixed
        value: "${DEFAULT_WAREHOUSE}"
      weight:
        generator: expression
        expr: "sum(inputs, 'telemetry.weight') + ${PALLET_TARE_WEIGHT_KG} * 1000"
      case_count:
        generator: count_inputs

  NONE:
    telemetry: {}
```

#### 2.3 Telemetry Generator

**New file**: `src/simpy_demo/factories/telemetry.py`
```python
class TelemetryGenerator:
    """Generate telemetry values from materials config."""

    GENERATORS = {
        "gaussian": GaussianGenerator,
        "fixed": FixedGenerator,
        "expression": ExpressionGenerator,
        "count_inputs": CountInputsGenerator,
    }

    def generate(self, material_type: str, inputs: list, env_now: float) -> dict:
        """Generate telemetry dict based on material type config."""
```

#### 2.4 Refactor Equipment

- Inject `TelemetryGenerator` into Equipment
- Replace hardcoded if/elif in `_transform_material()` with generator call
- Keep fallback for backward compatibility

---

### Phase 3: Graph Topology (v0.7.0)

**Goal**: DAG-based topology for branching, merging, rework loops

#### 3.1 Topology Graph

**New file**: `src/simpy_demo/topology/graph.py`
```python
@dataclass
class StationNode:
    name: str
    batch_in: int = 1
    output_type: MaterialType = MaterialType.NONE
    equipment_ref: Optional[str] = None
    behavior_ref: Optional[str] = None

@dataclass
class BufferEdge:
    source: str
    target: str
    capacity_override: Optional[int] = None
    condition: Optional[str] = None  # For quality gates

class TopologyGraph:
    def add_node(self, node: StationNode): ...
    def add_edge(self, edge: BufferEdge): ...
    def get_downstream(self, station: str) -> List[str]: ...
    def get_upstream(self, station: str) -> List[str]: ...
    def topological_order(self) -> Iterator[StationNode]: ...
```

#### 3.2 Enhanced Topology YAML

**`config/topologies/cosmetics_line.yaml`**
```yaml
name: cosmetics_line
materials: cosmetics
source: infinite_raw

nodes:
  - name: Filler
    batch_in: 1
    output_type: Tube
  - name: Inspector
    batch_in: 1
    output_type: None
  - name: Packer
    batch_in: 12
    output_type: Case
  - name: Palletizer
    batch_in: 60
    output_type: Pallet

edges:
  - source: _source
    target: Filler
  - source: Filler
    target: Inspector
  - source: Inspector
    target: Packer
    condition: "not product.is_defective"  # Quality gate
  - source: Inspector
    target: _reject
    condition: "product.is_defective"
  - source: Packer
    target: Palletizer
  - source: Palletizer
    target: _sink
```

#### 3.3 Layout Builder

**New file**: `src/simpy_demo/simulation/layout.py`
- Build SimPy layout from TopologyGraph
- Support multiple downstream connections (conditional routing)
- Handle `_source`, `_sink`, `_reject` special nodes

---

### Phase 4: Configurable Phases (v0.8.0)

**Goal**: Equipment behavior defined in YAML, not code

#### 4.1 Behavior Config

**`config/behaviors/default_6phase.yaml`**
```yaml
name: default_6phase
description: "Standard 6-phase equipment cycle"

phases:
  - name: collect
    handler: CollectPhase
    enabled: always

  - name: breakdown
    handler: BreakdownPhase
    enabled: "config.reliability.mtbf_min is not None"

  - name: microstop
    handler: MicrostopPhase
    enabled: "config.performance.jam_prob > 0"

  - name: execute
    handler: ExecutePhase
    enabled: always

  - name: transform
    handler: TransformPhase
    enabled: always

  - name: inspect
    handler: InspectPhase
    enabled: "config.quality.detection_prob > 0"
```

#### 4.2 Phase Handlers

**New directory**: `src/simpy_demo/behavior/phases/`
- Each phase is a separate module
- Common interface via `Phase` protocol
- `TransformPhase` uses `ProductFactory`

#### 4.3 Behavior Orchestrator

**New file**: `src/simpy_demo/behavior/orchestrator.py`
```python
class BehaviorOrchestrator:
    def should_run_phase(self, phase: PhaseConfig, equipment_config) -> bool: ...
    def run_cycle(self, equipment, inputs: list) -> Generator: ...
```

---

### Phase 4 Addendum: Deprecate Backwards Compatibility (v0.8.1)

**Goal**: Remove inline 6-phase cycle now that BehaviorOrchestrator is functional

#### Rationale

- Orchestrator produces identical results to inline implementation (verified)
- No external tests or code depend on inline implementation
- `config/behaviors/default_6phase.yaml` is auto-loaded, so orchestrator is always used
- Cleanup reduces maintenance burden (~170 lines removed)

#### 4A.1 Files to Modify

**`src/simpy_demo/equipment.py`** - Remove dead code:
- `_run_inline()` method (~76 lines)
- `_transform_material()` method (~39 lines) - logic already in `TransformPhase`
- `_run_with_orchestrator()` method - inline its contents into `run()`
- Remove `Optional` from `orchestrator` parameter - make it required

**`src/simpy_demo/engine.py`**:
- Always create `BehaviorOrchestrator` (use `DEFAULT_BEHAVIOR` if no config)
- Remove the `if resolved.behavior:` conditional

**`src/simpy_demo/loader.py`**:
- Always load default behavior if no explicit behavior specified
- Import and use `DEFAULT_BEHAVIOR` from behavior module

**`src/simpy_demo/simulation/layout.py`**:
- Make `orchestrator` parameter required in `LayoutBuilder.__init__()`

#### 4A.2 Execution Steps

1. Update loader.py - Always provide behavior config (use DEFAULT_BEHAVIOR)
2. Update engine.py - Remove conditional orchestrator creation
3. Update layout.py - Make orchestrator required
4. Simplify equipment.py - Remove inline code, inline orchestrator call
5. Update __init__.py exports if needed
6. Run verification - `poetry run python -m simpy_demo --run baseline_8hr`
7. Run ruff/mypy - Ensure code quality
8. Update CHANGELOG.md - Document changes

#### 4A.3 Expected Outcome

- Equipment.py reduced from ~330 lines to ~155 lines
- Single code path through behavior system
- Cleaner, more maintainable architecture
- No functional changes (identical simulation results)

---

### Phase 4B: Simplify Telemetry (v0.8.2)

**Goal**: Delete over-engineered expression engine, simplify telemetry to product-level attributes

#### Rationale

The expression engine was built to support config-driven telemetry with expressions like:
```yaml
weight:
  generator: expression
  expr: "sum(inputs, 'telemetry.weight') + ${CASE_TARE_WEIGHT_G}"
```

This is over-engineering. For the prototype, we only need:
- Product volume (e.g., `size_oz: 5.0`)
- Product net weight (e.g., `net_weight_g: 150.0`)

Pack weights (CASE/PALLET aggregation) aren't needed for this prototype.

#### 4B.1 Files to Delete

| Path | Lines | Reason |
|------|-------|--------|
| `src/simpy_demo/expressions/` | ~230 | Entire directory - expression engine not needed |
| `src/simpy_demo/factories/telemetry.py` | ~150 | TelemetryGenerator with expression/gaussian generators |
| `config/materials/cosmetics.yaml` | ~40 | Telemetry generator configs |

#### 4B.2 Files to Modify

**`src/simpy_demo/models.py`**:
- Add `net_weight_g: float` to `ProductConfig`

**`config/products/*.yaml`**:
```yaml
name: fresh_toothpaste_5oz
size_oz: 5.0
net_weight_g: 150.0  # NEW: simple product attribute
units_per_case: 12
cases_per_pallet: 60
```

**`src/simpy_demo/behavior/phases/transform.py`**:
- Remove TelemetryGenerator injection
- Product telemetry = simple dict from product config (volume, weight)
- No expressions, no aggregation

**`src/simpy_demo/equipment.py`**:
- Remove `telemetry_gen` parameter from `__init__`

**`src/simpy_demo/engine.py`**:
- Remove `TelemetryGenerator` creation in `_build_layout()`

**`src/simpy_demo/simulation/layout.py`**:
- Remove `telemetry_gen` from `LayoutBuilder`

**`src/simpy_demo/loader.py`**:
- Remove `MaterialsConfig` and `load_materials()`

**`src/simpy_demo/__init__.py`**:
- Remove exports: `ExpressionEngine`, `TelemetryGenerator`, `MaterialsConfig`

#### 4B.3 Execution Steps

1. Add `net_weight_g: float` to `ProductConfig` in `models.py`
2. Update `config/products/*.yaml` with net_weight values
3. Simplify `TransformPhase.execute()` - use product config directly
4. Remove `telemetry_gen` from `Equipment`, `LayoutBuilder`, `engine.py`
5. Delete `src/simpy_demo/expressions/` directory
6. Delete `src/simpy_demo/factories/telemetry.py`
7. Delete `config/materials/cosmetics.yaml`
8. Update `loader.py` - remove `MaterialsConfig`, `load_materials()`
9. Update `__init__.py` exports
10. Run verification - `poetry run python -m simpy_demo --run baseline_8hr`
11. Run linting - `poetry run ruff check src/ && poetry run mypy src/`
12. Update CHANGELOG.md

#### 4B.4 Expected Outcome

- ~400 lines of code deleted
- Telemetry simplified to product-level attributes
- No more expression parsing, no more "generator" abstraction
- Product config is the single source of truth for product attributes

---

### Phase 5: CLI & Scenario Generation (v0.9.0)

**Goal**: `configure` → `simulate` workflow with scenario bundling

#### 5.1 CLI Structure

**`src/simpy_demo/cli/configure.py`**
```python
def configure(run_name: str, output_dir: str = "scenarios/"):
    """
    Generate a standalone scenario from YAML configs.

    1. Load and resolve all configs
    2. Validate configuration
    3. Generate scenario.py from template
    4. Bundle config snapshot + metadata
    5. Return scenario path
    """
```

**`src/simpy_demo/cli/simulate.py`**
```python
def simulate(scenario_path: str, export: bool = False):
    """
    Run a scenario and generate output.

    1. Load scenario.py
    2. Execute simulation
    3. Export telemetry + events
    """
```

#### 5.2 Scenario Generation

**New file**: `src/simpy_demo/codegen/generator.py`
```python
class ScenarioGenerator:
    def generate(self, resolved_config: ResolvedConfig) -> str:
        """Generate scenario.py content from resolved config."""

    def bundle(self, scenario_py: str, config: ResolvedConfig, output_dir: str):
        """Create scenario bundle directory with all artifacts."""
```

**Template**: `src/simpy_demo/codegen/templates/scenario.py.j2`
```python
#!/usr/bin/env python3
"""
Scenario: {{ config.run.name }}
Generated: {{ timestamp }}
Config Hash: {{ config_hash }}
Git Commit: {{ git_commit }}
"""

SCENARIO_CONFIG = {{ config_json }}

from simpy_demo.simulation.runtime import execute_scenario

if __name__ == "__main__":
    execute_scenario(SCENARIO_CONFIG)
```

#### 5.3 Campaign Support

**`config/campaigns/weekly_skus.yaml`**
```yaml
name: weekly_skus
description: "Run all SKUs for weekly planning"

runs:
  - run: fresh_toothpaste_8hr
    product: fresh_toothpaste_5oz
  - run: mint_toothpaste_8hr
    product: mint_toothpaste_5oz
  - run: whitening_8hr
    product: whitening_toothpaste_5oz

output:
  aggregate: true  # Combine results
  format: csv
```

```bash
simpy-demo campaign --campaign weekly_skus --export
```

---

---

## Future Enhancements

> These features are deferred until there's a real use case. Revisit when needed.

### Multi-Line Support (formerly v1.0.0)

**Goal**: Simulate multiple production lines, share resources

**Plant-Level Config** (`config/plants/main_factory.yaml`):
```yaml
name: main_factory

lines:
  - name: line_1
    topology: cosmetics_line
    equipment_set: line_1_equipment
  - name: line_2
    topology: cosmetics_line
    equipment_set: line_2_equipment

shared_resources:
  - name: maintenance_crew
    capacity: 2
  - name: forklift
    capacity: 3
```

**Implementation Notes**:
- Run multiple lines in same SimPy environment
- Shared resources (maintenance, forklifts) as SimPy Resources
- Cross-line telemetry aggregation

---

## Detailed Implementation Notes

### Config Resolution Algorithm

The config system uses **layered inheritance** with this resolution order:

```
1. defaults.yaml          <- Global baseline
2. constants.yaml         <- Available for ${} substitution everywhere
3. {type}/_defaults.yaml  <- Type-specific defaults (optional)
4. {type}/{name}.yaml     <- Entity definition
5. scenarios/*.yaml       <- Scenario-level overrides
6. runs/*.yaml            <- Run-level overrides (most specific)
```

**Resolution pseudocode**:
```python
def resolve_config(run_name: str) -> ResolvedConfig:
    # 1. Load global defaults
    defaults = load_yaml("config/defaults.yaml")
    constants = load_yaml("config/constants.yaml")

    # 2. Load run config
    run = load_yaml(f"config/runs/{run_name}.yaml")

    # 3. Load and resolve scenario
    scenario = load_yaml(f"config/scenarios/{run.scenario}.yaml")

    # 4. Load topology
    topology = load_yaml(f"config/topologies/{scenario.topology}.yaml")

    # 5. Load equipment with inheritance
    equipment = {}
    for equip_name in scenario.equipment:
        base = deep_merge(defaults.equipment, load_yaml(f"config/equipment/{equip_name}.yaml"))
        if equip_name in scenario.overrides:
            base = deep_merge(base, scenario.overrides[equip_name])
        equipment[equip_name] = base

    # 6. Load materials and source
    materials = load_yaml(f"config/materials/{topology.materials}.yaml")
    source = load_yaml(f"config/sources/{topology.source}.yaml")

    # 7. Load product (optional)
    product = load_yaml(f"config/products/{run.product}.yaml") if run.product else None

    # 8. Substitute constants in all string values
    resolved = substitute_constants(
        ResolvedConfig(run, scenario, topology, equipment, materials, source, product),
        constants
    )

    return resolved
```

### Expression Engine Implementation

**Safe evaluation using AST parsing** (no `eval()`):

```python
import ast
import operator

class ExpressionEngine:
    """Safe expression evaluator using AST parsing."""

    OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
    }

    FUNCTIONS = {
        "sum": lambda inputs, field: sum(
            get_nested(i, field) for i in inputs
        ),
        "len": lambda inputs: len(inputs),
        "max": lambda inputs, field: max(
            get_nested(i, field) for i in inputs
        ),
        "min": lambda inputs, field: min(
            get_nested(i, field) for i in inputs
        ),
    }

    def __init__(self, constants: dict):
        self.constants = constants

    def evaluate(self, expr: str, context: dict) -> Any:
        # Step 1: Substitute ${CONSTANT} placeholders
        expr = self._substitute_constants(expr)

        # Step 2: Parse AST
        tree = ast.parse(expr, mode='eval')

        # Step 3: Evaluate safely
        return self._eval_node(tree.body, context)

    def _substitute_constants(self, expr: str) -> str:
        import re
        pattern = r'\$\{(\w+)\}'
        def replace(match):
            key = match.group(1)
            if key not in self.constants:
                raise ValueError(f"Unknown constant: {key}")
            return str(self.constants[key])
        return re.sub(pattern, replace, expr)

    def _eval_node(self, node, context):
        if isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left, context)
            right = self._eval_node(node.right, context)
            return self.OPERATORS[type(node.op)](left, right)
        elif isinstance(node, ast.Call):
            func_name = node.func.id
            if func_name not in self.FUNCTIONS:
                raise ValueError(f"Unknown function: {func_name}")
            args = [self._eval_node(arg, context) for arg in node.args]
            # Handle inputs reference
            if args[0] == 'inputs':
                args[0] = context['inputs']
            return self.FUNCTIONS[func_name](*args)
        elif isinstance(node, ast.Name):
            if node.id == 'inputs':
                return 'inputs'  # Placeholder for function calls
            raise ValueError(f"Unknown variable: {node.id}")
        else:
            raise ValueError(f"Unsupported AST node: {type(node)}")
```

### Phase Handler Interface

```python
# src/simpy_demo/behavior/phases/base.py

from abc import ABC, abstractmethod
from typing import Generator, List, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from simpy_demo.simulation.equipment import Equipment
    from simpy_demo.models import Product

class Phase(ABC):
    """Base class for equipment behavior phases."""

    name: str  # Phase name for logging

    @abstractmethod
    def execute(
        self,
        equipment: "Equipment",
        inputs: List["Product"],
        **params
    ) -> Generator[Any, None, Any]:
        """
        Execute the phase.

        Args:
            equipment: The equipment instance
            inputs: Products collected from upstream
            **params: Phase-specific parameters from behavior config

        Yields:
            SimPy events (timeout, store.get, store.put, etc.)

        Returns:
            Phase-specific result (e.g., transformed Product)
        """
        pass

    def is_enabled(self, equipment: "Equipment") -> bool:
        """Check if phase should run based on equipment config."""
        return True


# Example: CollectPhase
class CollectPhase(Phase):
    name = "collect"

    def execute(self, equipment, inputs, **params):
        """Collect batch_in items from upstream."""
        collected = []
        for _ in range(equipment.cfg.batch_in):
            item = yield equipment.upstream.get()
            collected.append(item)
        return collected


# Example: BreakdownPhase
class BreakdownPhase(Phase):
    name = "breakdown"

    def is_enabled(self, equipment):
        return equipment.cfg.reliability.mtbf_min is not None

    def execute(self, equipment, inputs, distribution="poisson", **params):
        """Check for breakdown, repair if needed."""
        import random
        import math

        mtbf_sec = equipment.cfg.reliability.mtbf_min * 60
        cycle_time = equipment.cfg.cycle_time_sec
        p_fail = 1 - math.exp(-cycle_time / mtbf_sec)

        if random.random() < p_fail:
            # Machine failed
            equipment.log("DOWN")
            mttr_sec = random.expovariate(1 / (equipment.cfg.reliability.mttr_min * 60))
            yield equipment.env.timeout(mttr_sec)
            equipment.log("EXECUTE")

        return None  # No output from this phase
```

### Semgrep Rules - Complete Set

```yaml
# .semgrep/rules/hardcoded-values.yaml
rules:
  # ============================================
  # TELEMETRY HARDCODES
  # ============================================
  - id: simpy-hardcoded-gaussian-telemetry
    patterns:
      - pattern: random.gauss($MEAN, $STD)
      - pattern-not: random.gauss(mean, std)
      - pattern-not: random.gauss(self.mean, self.std)
    message: |
      Hardcoded gaussian parameters detected.
      Move to config/materials/*.yaml with generator: gaussian
    languages: [python]
    severity: WARNING
    paths:
      include: [src/simpy_demo/]

  - id: simpy-hardcoded-location-string
    pattern-regex: '["'']Warehouse_\w+["'']'
    message: |
      Hardcoded warehouse location.
      Move to config/constants.yaml as DEFAULT_WAREHOUSE
    languages: [python]
    severity: WARNING
    paths:
      include: [src/simpy_demo/]

  # ============================================
  # INVENTORY/COUNT HARDCODES
  # ============================================
  - id: simpy-hardcoded-large-range
    patterns:
      - pattern: range($NUM)
      - metavariable-comparison:
          metavariable: $NUM
          comparison: $NUM > 1000
    message: |
      Large hardcoded range detected.
      Move to config/sources/*.yaml as initial_inventory
    languages: [python]
    severity: WARNING
    paths:
      include: [src/simpy_demo/]

  - id: simpy-hardcoded-for-range
    patterns:
      - pattern: |
          for $VAR in range($NUM):
              ...
      - metavariable-comparison:
          metavariable: $NUM
          comparison: $NUM > 100
    message: |
      Large hardcoded iteration count.
      Consider making configurable.
    languages: [python]
    severity: INFO
    paths:
      include: [src/simpy_demo/]

  # ============================================
  # TIME CONVERSION HARDCODES
  # ============================================
  - id: simpy-magic-seconds-per-hour
    patterns:
      - pattern-either:
          - pattern: $X * 3600
          - pattern: $X / 3600
          - pattern: 3600 * $X
          - pattern: 3600 / $X
      - pattern-not: SECONDS_PER_HOUR * $X
      - pattern-not: $X * SECONDS_PER_HOUR
    message: |
      Magic number 3600 (seconds per hour).
      Use SECONDS_PER_HOUR from constants.yaml
    languages: [python]
    severity: INFO
    paths:
      include: [src/simpy_demo/]

  - id: simpy-magic-seconds-per-minute
    patterns:
      - pattern-either:
          - pattern: $X * 60
          - pattern: $X / 60
          - pattern: 60 * $X
          - pattern: 60 / $X
      - pattern-not: SECONDS_PER_MINUTE * $X
      - pattern-not: $X * SECONDS_PER_MINUTE
      - pattern-not-inside: |
          def $FUNC(...):
              ...
              $X * 60
              ...
    message: |
      Magic number 60 (seconds per minute).
      Use SECONDS_PER_MINUTE from constants.yaml
    languages: [python]
    severity: INFO
    paths:
      include: [src/simpy_demo/]

  # ============================================
  # DEFAULT VALUE HARDCODES
  # ============================================
  - id: simpy-hardcoded-buffer-capacity
    patterns:
      - pattern: buffer_capacity=$NUM
      - metavariable-comparison:
          metavariable: $NUM
          comparison: $NUM > 10
    message: |
      Hardcoded buffer_capacity default.
      Move to config/defaults.yaml
    languages: [python]
    severity: WARNING
    paths:
      include: [src/simpy_demo/]

  - id: simpy-hardcoded-cost-rates
    patterns:
      - pattern-either:
          - pattern: labor_per_hour=$NUM
          - pattern: energy_per_hour=$NUM
          - pattern: overhead_per_hour=$NUM
    message: |
      Hardcoded cost rate default.
      Move to config/defaults.yaml
    languages: [python]
    severity: WARNING
    paths:
      include: [src/simpy_demo/]

  # ============================================
  # EQUIPMENT NAME HARDCODES
  # ============================================
  - id: simpy-hardcoded-equipment-name-string
    patterns:
      - pattern: '"$NAME"'
      - metavariable-regex:
          metavariable: $NAME
          regex: '(Filler|Packer|Palletizer|Inspector|Raw)'
    message: |
      Hardcoded equipment name.
      Use config reference or constant.
    languages: [python]
    severity: INFO
    paths:
      include: [src/simpy_demo/]
```

### Config Snapshot Schema

**`config_snapshot.yaml`** (generated by `configure` command):

```yaml
# Auto-generated frozen configuration
# DO NOT EDIT - regenerate with: simpy-demo configure --run baseline_8hr

_meta:
  generated_at: "2025-01-26T14:30:22Z"
  config_hash: "sha256:abc123..."
  run_name: baseline_8hr

run:
  name: baseline_8hr
  scenario: baseline
  product: fresh_toothpaste_5oz
  duration_hours: 8.0
  random_seed: 42
  telemetry_interval_sec: 300.0
  start_time: "2025-01-06T06:00:00"

scenario:
  name: baseline
  topology: cosmetics_line
  equipment:
    - Filler
    - Inspector
    - Packer
    - Palletizer
  overrides: {}

topology:
  name: cosmetics_line
  materials: cosmetics
  source: infinite_raw
  nodes:
    - name: Filler
      batch_in: 1
      output_type: Tube
    # ... full topology

equipment:
  Filler:
    name: Filler
    uph: 12000
    buffer_capacity: 100
    reliability:
      mtbf_min: 480
      mttr_min: 15
    # ... full equipment config

materials:
  name: cosmetics
  types:
    TUBE:
      telemetry:
        fill_level:
          generator: gaussian
          mean: 100
          stddev: 1.0
    # ... full materials config

source:
  name: infinite_raw
  initial_inventory: 100000
  material_type: "None"
  parent_machine: "Raw"

product:
  name: fresh_toothpaste_5oz
  description: "Fresh Toothpaste 5oz Tube"
  size_oz: 5.0
  units_per_case: 12
  cases_per_pallet: 60
  material_cost: 150.0
  selling_price: 450.0

constants:
  TUBE_WEIGHT_G: 100
  CASE_TARE_WEIGHT_G: 50
  NOMINAL_FILL_LEVEL_ML: 100
  FILL_STDDEV_ML: 1.0
  DEFAULT_WAREHOUSE: "Warehouse_A"
  SECONDS_PER_HOUR: 3600
  SECONDS_PER_MINUTE: 60
```

---

## Critique & Improvements

### What's Good About This Plan
1. **Incremental delivery** - Each phase is independently valuable
2. **Backward compatible** - `run` command continues to work
3. **Semgrep guardrails** - Prevents new hardcodes from creeping in
4. **Auditable** - Scenario bundling enables reproducibility

### Potential Issues & Mitigations

| Issue | Risk | Mitigation |
|-------|------|------------|
| Expression engine security | Code injection via eval | Use AST parsing, whitelist functions |
| Scenario file size | Large configs = huge scenario.py | Compress config, lazy load |
| Graph complexity | DAG cycles cause infinite loops | Validate acyclic on load |
| Phase ordering | Wrong order breaks simulation | Validate phase dependencies |
| Campaign performance | Many runs = slow | Parallel execution option |

### Suggested Improvements

1. **Add scenario diffing**: Compare two scenarios to see config changes
   ```bash
   simpy-demo diff scenarios/baseline_v1/ scenarios/baseline_v2/
   ```

2. **Add dry-run mode**: Validate config without running simulation
   ```bash
   simpy-demo configure --run baseline_8hr --dry-run
   ```

3. **Add config linting**: Validate YAML before configure
   ```bash
   simpy-demo lint config/
   ```

4. **Add scenario replay**: Re-run scenario with same seed for debugging
   ```bash
   simpy-demo simulate --scenario scenarios/baseline_8hr_* --replay
   ```

5. **Add telemetry streaming**: For long simulations, stream to database
   ```bash
   simpy-demo simulate --scenario ... --stream-to postgres://...
   ```

---

## Version Milestones

| Version | Phase | Key Deliverable |
|---------|-------|-----------------|
| v0.4.2 | 0 | Semgrep rules + baseline scan |
| v0.5.0 | 1 | Config foundation (defaults, constants, source) |
| v0.6.0 | 2 | ~~Expression engine~~ (removed in v0.8.2) |
| v0.7.0 | 3 | Graph topology abstraction |
| v0.8.0 | 4 | Configurable equipment phases |
| v0.8.1 | 4A | Deprecate backwards compatibility (cleanup) |
| v0.8.2 | 4B | Simplify telemetry (delete expression engine) |
| v0.9.0 | 5 | CLI commands + scenario generation + campaigns |

**Deferred to Future Enhancement:**
- v1.0.0 Multi-line support (revisit when there's a real use case)

---

## Testing Strategy

### Per-Phase Verification
```bash
# 1. Run semgrep (should pass after fixes)
semgrep --config .semgrep/rules/ src/simpy_demo/ --error

# 2. Run existing simulation (should produce identical output)
poetry run python -m simpy_demo --run baseline_8hr --export
diff baseline.csv output/telemetry_*.csv

# 3. Linting & type checking
poetry run ruff check src/
poetry run mypy src/
```

### New Tests to Add
- Unit tests for ExpressionEngine
- Unit tests for TopologyGraph (cycle detection, topological sort)
- Unit tests for BehaviorOrchestrator
- Integration tests for configure → simulate workflow
- Property tests for telemetry generators

---

## Critical Files to Read Before Implementation

1. `src/simpy_demo/equipment.py` - 6-phase cycle (92-160), transform (162-217)
2. `src/simpy_demo/engine.py` - build_layout, monitor_process, compile_results
3. `src/simpy_demo/loader.py` - Current config resolution
4. `config/materials/cosmetics.yaml` - Unused, will become telemetry source
5. `src/simpy_demo/models.py` - Pydantic schemas to extend

---

## Quick Start for Fresh Session

When starting a fresh Claude Code session, reference this document:

```
Read refac3.md and continue with Phase 0 (semgrep setup)
```

### Phase 0 Commands (First Session)

```bash
# 1. Create semgrep directory structure
mkdir -p .semgrep/rules .semgrep/tests

# 2. Create hardcoded-values.yaml (from this doc)

# 3. Install semgrep if needed
pip install semgrep

# 4. Run baseline scan
semgrep --config .semgrep/rules/ src/simpy_demo/ --json > .semgrep/baseline_scan.json

# 5. Count findings
cat .semgrep/baseline_scan.json | jq '.results | length'

# 6. Add pre-commit hook (optional)
# Update .pre-commit-config.yaml
```

### Version Checklist

- [x] v0.4.2 - Semgrep rules + baseline scan
- [x] v0.5.0 - Config foundation (defaults, constants, source)
- [x] v0.6.0 - ~~Expression engine~~ (superseded by v0.8.2)
- [x] v0.7.0 - Graph topology abstraction
- [x] v0.8.0 - Configurable equipment phases
- [x] v0.8.1 - Deprecate backwards compatibility (cleanup)
- [x] v0.8.2 - Simplify telemetry (delete expression engine)
- [ ] v0.9.0 - CLI commands + scenario generation + campaigns

**Deferred:**
- [ ] Multi-line support (formerly v1.0.0) - see Future Enhancements
