# Digital Twin Refactor Plan

## Goal
Refactor the simulation into a proper digital twin architecture that separates:
1. **Asset definitions** (what exists) from **behavior** (how it works)
2. **Topology** (structure) from **configuration** (parameters)
3. **Twin definition** (the model) from **scenarios** (what-if experiments)

## Current State
```
src/simpy_demo/
├── models.py      # Pydantic schemas (mixed concerns)
├── equipment.py   # SmartEquipment simulation logic
├── simulation.py  # ProductionLine engine
├── scenarios.py   # Hardcoded line config + run logic
```

Problems:
- Line topology and parameters are bundled together in scenarios.py
- Can't run different parameter scenarios without redefining the whole line
- Depalletizer is redundant (just passes through from infinite source)
- Naming doesn't reflect digital twin concepts

## Target Architecture
```
src/simpy_demo/
├── __init__.py
├── __main__.py
├── twin/
│   ├── __init__.py
│   ├── assets/
│   │   ├── __init__.py
│   │   ├── equipment.py    # Equipment type definitions
│   │   └── materials.py    # Material types (Tube, Case, Pallet)
│   ├── behaviors/
│   │   ├── __init__.py
│   │   └── reliability.py  # MTBF/MTTR, jam logic, defect models
│   └── topology/
│       ├── __init__.py
│       └── cosmetics_line.py  # Line structure (Filler→Inspector→Packer→Palletizer)
├── scenarios/
│   ├── __init__.py
│   ├── config.py           # ScenarioConfig, EquipmentParams schemas
│   └── baseline.py         # Default parameter values
├── simulation/
│   ├── __init__.py
│   └── engine.py           # SimPy execution engine
└── run.py                  # Entry point
```

## Key Design Decisions

### 1. Remove Depalletizer
The infinite source is handled implicitly by the simulation engine. The line becomes:
```
[Source] → Filler → Inspector → Packer → Palletizer → [Sink]
```

### 2. Topology Definition (define once)
```python
# twin/topology/cosmetics_line.py
class CosmeticsLine:
    """Cosmetics production line topology."""

    stations = [
        Station(name="Filler", type=StationType.PROCESSOR,
                input=MaterialType.TUBE, output=MaterialType.TUBE, batch_in=1),
        Station(name="Inspector", type=StationType.INSPECTOR, batch_in=1),
        Station(name="Packer", type=StationType.AGGREGATOR,
                input=MaterialType.TUBE, output=MaterialType.CASE, batch_in=12),
        Station(name="Palletizer", type=StationType.AGGREGATOR,
                input=MaterialType.CASE, output=MaterialType.PALLET, batch_in=60),
    ]
```

### 3. Scenario Configuration (vary per run)
```python
# scenarios/config.py
class EquipmentParams(BaseModel):
    """Parameters that can vary per scenario."""
    uph: Optional[int] = None
    mtbf_min: Optional[float] = None
    mttr_min: Optional[float] = None
    jam_prob: Optional[float] = None
    jam_time_sec: Optional[float] = None
    buffer_capacity: Optional[int] = None
    defect_rate: Optional[float] = None
    detection_prob: Optional[float] = None

class ScenarioConfig(BaseModel):
    """A scenario = run parameters + equipment parameter overrides."""
    name: str
    duration_hours: float = 8.0
    random_seed: Optional[int] = 42
    equipment: Dict[str, EquipmentParams] = {}  # overrides by station name
```

### 4. Baseline Defaults
```python
# scenarios/baseline.py
BASELINE = {
    "Filler": EquipmentParams(
        uph=10000, buffer_capacity=50, mtbf_min=120, mttr_min=15,
        jam_prob=0.01, jam_time_sec=15, defect_rate=0.02
    ),
    "Inspector": EquipmentParams(
        uph=11000, buffer_capacity=20, detection_prob=0.95
    ),
    "Packer": EquipmentParams(
        uph=12000, buffer_capacity=100, mtbf_min=240,
        jam_prob=0.05, jam_time_sec=30
    ),
    "Palletizer": EquipmentParams(
        uph=13000, buffer_capacity=40, mtbf_min=480
    ),
}
```

### 5. Running Scenarios
```python
# run.py
from simpy_demo.twin.topology.cosmetics_line import CosmeticsLine
from simpy_demo.scenarios.baseline import BASELINE
from simpy_demo.scenarios.config import ScenarioConfig, EquipmentParams
from simpy_demo.simulation.engine import SimulationEngine

# Define a scenario (just the overrides)
scenario = ScenarioConfig(
    name="large_buffer_test",
    equipment={
        "Filler": EquipmentParams(buffer_capacity=500)
    }
)

# Run
engine = SimulationEngine(CosmeticsLine(), BASELINE)
results = engine.run(scenario)
```

## Implementation Steps

### Phase 1: Create directory structure
1. Create `twin/`, `twin/assets/`, `twin/behaviors/`, `twin/topology/`
2. Create `scenarios/`
3. Create `simulation/`

### Phase 2: Migrate assets
1. Move `MaterialType`, `Product` → `twin/assets/materials.py`
2. Create `StationType` enum, `Station` schema → `twin/assets/equipment.py`

### Phase 3: Migrate behaviors
1. Extract reliability logic from SmartEquipment → `twin/behaviors/reliability.py`
2. Keep SmartEquipment as the SimPy process wrapper

### Phase 4: Create topology
1. Create `CosmeticsLine` in `twin/topology/cosmetics_line.py`
2. Remove Depalletizer from the line

### Phase 5: Create scenarios
1. Create `EquipmentParams`, `ScenarioConfig` → `scenarios/config.py`
2. Create baseline defaults → `scenarios/baseline.py`

### Phase 6: Refactor simulation engine
1. Move `ProductionLine` → `simulation/engine.py` as `SimulationEngine`
2. Update to accept topology + baseline + scenario
3. Merge baseline with scenario overrides when building

### Phase 7: Create entry point
1. Create `run.py` with example usage
2. Update `__main__.py`

### Phase 8: Cleanup
1. Delete old flat files (models.py, equipment.py, simulation.py, scenarios.py)
2. Update `__init__.py` exports
3. Update CLAUDE.md and README.md

## Files Summary

### Delete
- `src/simpy_demo/models.py`
- `src/simpy_demo/equipment.py`
- `src/simpy_demo/simulation.py`
- `src/simpy_demo/scenarios.py`

### Create
- `src/simpy_demo/twin/__init__.py`
- `src/simpy_demo/twin/assets/__init__.py`
- `src/simpy_demo/twin/assets/materials.py`
- `src/simpy_demo/twin/assets/equipment.py`
- `src/simpy_demo/twin/behaviors/__init__.py`
- `src/simpy_demo/twin/behaviors/reliability.py`
- `src/simpy_demo/twin/topology/__init__.py`
- `src/simpy_demo/twin/topology/cosmetics_line.py`
- `src/simpy_demo/scenarios/__init__.py`
- `src/simpy_demo/scenarios/config.py`
- `src/simpy_demo/scenarios/baseline.py`
- `src/simpy_demo/simulation/__init__.py`
- `src/simpy_demo/simulation/engine.py`
- `src/simpy_demo/run.py`

### Update
- `src/simpy_demo/__init__.py`
- `src/simpy_demo/__main__.py`
- `CLAUDE.md`
- `README.md`
