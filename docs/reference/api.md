# API Reference

Python API for programmatic use of SimPy-Demo.

## Core Classes

### SimulationEngine

Main entry point for running simulations.

```python
from simpy_demo import SimulationEngine

engine = SimulationEngine(config_dir="config")
```

#### Constructor

```python
SimulationEngine(config_dir: str = "config")
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `config_dir` | str | Path to configuration directory |

#### Methods

##### run

```python
def run(self, run_name: str) -> tuple[pd.DataFrame, pd.DataFrame]
```

Run a simulation by config name.

| Parameter | Type | Description |
|-----------|------|-------------|
| `run_name` | str | Name of run config (without .yaml) |

**Returns**: Tuple of (telemetry_df, events_df)

**Example**:
```python
df_telemetry, df_events = engine.run("baseline_8hr")
```

##### run_resolved

```python
def run_resolved(self, resolved: ResolvedConfig) -> tuple[pd.DataFrame, pd.DataFrame]
```

Run from a pre-resolved configuration.

**Example**:
```python
loader = ConfigLoader("config")
resolved = loader.resolve_run("baseline_8hr")
resolved.equipment["Filler"].buffer_capacity = 500  # Modify
df_ts, df_ev = engine.run_resolved(resolved)
```

##### run_config

```python
def run_config(
    self,
    run: RunConfig,
    machine_configs: list[MachineConfig],
    product: ProductConfig | None = None,
    source: SourceConfig | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]
```

Run from explicit configuration objects.

---

### ConfigLoader

Loads and resolves YAML configurations.

```python
from simpy_demo import ConfigLoader

loader = ConfigLoader(config_dir="config")
```

#### Methods

##### resolve_run

```python
def resolve_run(self, run_name: str) -> ResolvedConfig
```

Fully resolve a run configuration.

**Example**:
```python
resolved = loader.resolve_run("baseline_8hr")
print(resolved.run.duration_hours)  # 8.0
print(resolved.equipment["Filler"].uph)  # 4000
```

##### load_run

```python
def load_run(self, name: str) -> RunConfig
```

Load a run config by name.

##### load_scenario

```python
def load_scenario(self, name: str) -> ScenarioConfig
```

Load a scenario config by name.

##### load_topology

```python
def load_topology(self, name: str) -> TopologyConfig
```

Load a topology config by name.

##### load_equipment

```python
def load_equipment(self, name: str) -> EquipmentConfig
```

Load an equipment config by name.

##### load_product

```python
def load_product(self, name: str) -> ProductConfig
```

Load a product config by name.

##### build_machine_configs

```python
def build_machine_configs(self, resolved: ResolvedConfig) -> list[MachineConfig]
```

Build MachineConfig objects from resolved configuration.

---

### MachineConfig

Pydantic model for equipment configuration.

```python
from simpy_demo import MachineConfig

config = MachineConfig(
    name="Filler",
    uph=4000,
    batch_in=1,
    output_type="Tube",
    buffer_capacity=200,
    reliability=ReliabilityParams(mtbf_min=3600, mtbf_max=7200),
    performance=PerformanceParams(jam_prob=0.002),
    quality=QualityParams(defect_rate=0.01),
    cost_rates=CostRates(labor_per_hour=25.0)
)
```

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Equipment name |
| `uph` | int | Units per hour |
| `batch_in` | int | Input batch size |
| `output_type` | str | Output material type |
| `buffer_capacity` | int | Output buffer capacity |
| `reliability` | ReliabilityParams | Availability parameters |
| `performance` | PerformanceParams | Performance parameters |
| `quality` | QualityParams | Quality parameters |
| `cost_rates` | CostRates | Economic parameters |

#### Properties

##### cycle_time_sec

```python
@property
def cycle_time_sec(self) -> float
```

Cycle time in seconds (3600 / uph).

---

### Product

Pydantic model for a product flowing through the line.

```python
from simpy_demo import Product, MaterialType

product = Product(
    uid="P001",
    type=MaterialType.TUBE,
    created_at=0.0,
    parent_machine="Filler"
)
```

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `uid` | str | Unique identifier |
| `type` | MaterialType | TUBE, CASE, PALLET, NONE |
| `created_at` | float | Simulation time created |
| `parent_machine` | str | Machine that created it |
| `is_defective` | bool | Whether product is defective |
| `genealogy` | list | Parent products |
| `telemetry` | dict | Product telemetry data |

---

### Equipment

SimPy process representing a machine.

```python
from simpy_demo import Equipment

equipment = Equipment(
    env=env,
    config=machine_config,
    upstream=upstream_store,
    downstream=downstream_store,
    reject_bin=reject_store,
    orchestrator=orchestrator
)
```

Not typically instantiated directly; created by SimulationEngine.

---

## Parameter Classes

### ReliabilityParams

```python
from simpy_demo import ReliabilityParams

params = ReliabilityParams(
    mtbf_min=3600,    # Min time between failures (seconds)
    mtbf_max=7200,    # Max time between failures
    mttr_min=120,     # Min repair time
    mttr_max=300      # Max repair time
)
```

### PerformanceParams

```python
from simpy_demo import PerformanceParams

params = PerformanceParams(
    jam_prob=0.002,      # Probability of jam per cycle
    jam_time_sec=30      # Jam duration
)
```

### QualityParams

```python
from simpy_demo import QualityParams

params = QualityParams(
    defect_rate=0.01,       # Probability of defect
    detection_prob=0.95     # Probability of detecting defect
)
```

### CostRates

```python
from simpy_demo import CostRates

rates = CostRates(
    labor_per_hour=25.0,
    energy_per_hour=15.0,
    overhead_per_hour=10.0
)
```

---

## Behavior System

### BehaviorOrchestrator

Coordinates equipment phase execution.

```python
from simpy_demo import BehaviorOrchestrator, DEFAULT_BEHAVIOR

orchestrator = BehaviorOrchestrator(DEFAULT_BEHAVIOR)
```

### Phase Classes

Individual phase implementations:

- `CollectPhase` - Collect inputs from upstream
- `BreakdownPhase` - Check for breakdowns
- `MicrostopPhase` - Check for jams
- `ExecutePhase` - Process time
- `TransformPhase` - Create output product
- `InspectPhase` - Quality inspection

---

## Topology System

### TopologyGraph

DAG-based topology representation.

```python
from simpy_demo import TopologyGraph

graph = TopologyGraph()
graph.add_node(StationNode(name="Filler", output_type="Tube"))
graph.add_edge(BufferEdge(source="_source", target="Filler"))
```

### StationNode

```python
from simpy_demo import StationNode

node = StationNode(
    name="Filler",
    batch_in=1,
    output_type="Tube",
    equipment_ref="filler"
)
```

### BufferEdge

```python
from simpy_demo import BufferEdge

edge = BufferEdge(
    source="Filler",
    target="Inspector",
    capacity=200,
    condition="not product.is_defective"
)
```

---

## Code Generation

### ScenarioGenerator

Generates scenario bundles for reproducible runs.

```python
from simpy_demo import ScenarioGenerator

generator = ScenarioGenerator(config_dir="config")
bundle_path = generator.generate("baseline_8hr", output_dir="scenarios")
```

### execute_scenario

Run a scenario from a bundle.

```python
from simpy_demo import execute_scenario
from pathlib import Path

execute_scenario(Path("scenarios/baseline_8hr_20250129_143022"))
```

---

## Enums

### MaterialType

```python
from simpy_demo import MaterialType

MaterialType.TUBE
MaterialType.CASE
MaterialType.PALLET
MaterialType.NONE
```

---

## Database Storage

### save_results

Save simulation results to DuckDB.

```python
from simpy_demo import save_results

run_id = save_results(resolved, df_telemetry, df_events)
print(f"Saved as run_id: {run_id}")
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `resolved` | ResolvedConfig | Resolved configuration |
| `df_ts` | pd.DataFrame | Telemetry DataFrame |
| `df_ev` | pd.DataFrame | Events DataFrame |
| `db_path` | Path \| str \| None | Custom database path (default: `./simpy_results.duckdb`) |

**Returns**: `int` - The run_id for the saved simulation

### db_connect

Get a DuckDB connection for queries.

```python
from simpy_demo import db_connect

conn = db_connect()

# Query runs
df = conn.execute("SELECT * FROM v_run_comparison").df()

# Query OEE
oee = conn.execute("SELECT * FROM v_machine_oee WHERE run_id = 1").df()
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `db_path` | Path \| str \| None | Custom database path |

**Returns**: `duckdb.DuckDBPyConnection`

### get_db_path

Get the default database path.

```python
from simpy_demo import get_db_path

path = get_db_path()  # Path("./simpy_results.duckdb")
```

---

## Full Example

```python
from simpy_demo import (
    SimulationEngine,
    ConfigLoader,
    MachineConfig,
    ReliabilityParams,
    db_connect,
)

# Load and modify configuration
loader = ConfigLoader("config")
resolved = loader.resolve_run("baseline_8hr")

# Modify equipment parameters
resolved.equipment["Filler"].buffer_capacity = 500
resolved.equipment["Filler"].reliability = ReliabilityParams(
    mtbf_min=7200,
    mtbf_max=14400,
    mttr_min=60,
    mttr_max=150
)

# Run simulation (auto-saves to DuckDB)
engine = SimulationEngine("config")
df_telemetry, df_events = engine.run_resolved(resolved)

# Analyze results
print(f"Total pallets: {df_telemetry['pallets_produced'].sum()}")
print(f"Total revenue: ${df_telemetry['revenue'].sum():,.2f}")

# Query from database
conn = db_connect()
comparison = conn.execute("SELECT * FROM v_run_comparison").df()
print(comparison)
```
