# Digital Twin Refactor Plan v2

## Overview

Refactor the SimPy simulation into a proper digital twin architecture that separates:
1. **Topology** (line structure) from **Configuration** (parameters)
2. **Baseline** (defaults) from **Scenarios** (what-if experiments)
3. Keep **emergent behavior** driven by config (no separate behavior classes)

## Current vs Target

### Current Structure
```
src/simpy_demo/
├── models.py      # MachineConfig with flat params, Product, MaterialType
├── equipment.py   # SmartEquipment (monolithic machine simulator)
├── simulation.py  # ProductionLine (builds and runs simulation)
├── scenarios.py   # Hardcoded line config + run logic (DELETE)
```

### Target Structure
```
src/simpy_demo/
├── __init__.py
├── __main__.py
├── models.py           # Pydantic schemas with grouped params
├── equipment.py        # Equipment class (renamed from SmartEquipment)
├── topology.py         # NEW: CosmeticsLine definition (structure only)
├── config.py           # NEW: ScenarioConfig + EquipmentParams (overrides)
├── baseline.py         # NEW: Default parameter values
├── engine.py           # Renamed from simulation.py, updated interface
└── run.py              # NEW: Entry point with example usage
```

## How Behavior Works (Emergent from Config)

The `Equipment` class is a **generic machine simulator**. It follows a 6-phase cycle where **config params determine which behaviors activate**:

```
PHASE 1: COLLECT        <- Always runs (wait for upstream material)
    |
    v
PHASE 2: BREAKDOWN      <- Only if reliability.mtbf_min is set
    |                      - Poisson probability -> go DOWN
    |                      - Exponential repair time (mttr_min)
    v
PHASE 3: MICROSTOP      <- Only if performance.jam_prob > 0
    |                      - Bernoulli per cycle -> JAMMED
    |                      - Fixed wait (jam_time_sec)
    v
PHASE 4: EXECUTE        <- Always runs (wait cycle_time_sec)
    |
    v
PHASE 5: TRANSFORM      <- Based on output_type + quality.defect_rate
    |                      - Creates TUBE/CASE/PALLET based on config
    |                      - Bernoulli defect creation
    v
PHASE 6: INSPECT/ROUTE  <- Only if quality.detection_prob > 0
    |                      - Route defectives to reject bin
    |
    +--------------------> Loop back to PHASE 1
```

**All machines use the same code - config makes them different:**
- Filler: has breakdowns, jams, creates defects, outputs TUBEs
- Inspector: only has detection_prob, passes through
- Packer: batch_in=12, aggregates tubes into CASEs
- Palletizer: batch_in=60, aggregates cases into PALLETs

---

## File-by-File Implementation

### 1. models.py - Grouped Config Sub-Models

Add these new Pydantic models. Keep `Product` and `MaterialType` unchanged.

```python
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class MaterialType(str, Enum):
    """Material types in the production hierarchy."""
    TUBE = "Tube"
    CASE = "Case"
    PALLET = "Pallet"
    NONE = "None"


class Product(BaseModel):
    """A physical item flowing through the production line."""
    uid: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: MaterialType
    created_at: float
    parent_machine: str
    is_defective: bool = False
    genealogy: List[str] = Field(default_factory=list)
    telemetry: Dict[str, Any] = Field(default_factory=dict)


# --- NEW: Grouped parameter sub-models ---

class ReliabilityParams(BaseModel):
    """Availability loss parameters (MTBF/MTTR)."""
    mtbf_min: Optional[float] = None  # Mean Time Between Failures (minutes)
    mttr_min: float = 60.0            # Mean Time To Repair (minutes)


class PerformanceParams(BaseModel):
    """Performance loss parameters (microstops/jams)."""
    jam_prob: float = 0.0             # Probability per cycle
    jam_time_sec: float = 10.0        # Fixed jam clearance time


class QualityParams(BaseModel):
    """Quality loss parameters (defects/inspection)."""
    defect_rate: float = 0.0          # Probability of creating defect
    detection_prob: float = 0.0       # Inspection accuracy


class MachineConfig(BaseModel):
    """Complete machine configuration with grouped parameters."""
    name: str
    uph: int                          # Units Per Hour
    batch_in: int = 1
    output_type: MaterialType = MaterialType.NONE
    buffer_capacity: int = 50

    reliability: ReliabilityParams = Field(default_factory=ReliabilityParams)
    performance: PerformanceParams = Field(default_factory=PerformanceParams)
    quality: QualityParams = Field(default_factory=QualityParams)

    @property
    def cycle_time_sec(self) -> float:
        """Seconds per cycle (derived from UPH)."""
        return 3600.0 / self.uph
```

### 2. topology.py - Line Structure Definition (NEW)

```python
"""Production line topology definitions (structure only, no parameters)."""

from simpy_demo.models import MaterialType


class Station:
    """Defines a station in the production line (structure only, no params)."""

    def __init__(
        self,
        name: str,
        batch_in: int = 1,
        output_type: MaterialType = MaterialType.NONE,
    ):
        self.name = name
        self.batch_in = batch_in
        self.output_type = output_type


class CosmeticsLine:
    """Cosmetics production line topology.

    Line structure: [Source] -> Filler -> Inspector -> Packer -> Palletizer -> [Sink]

    Note: Depalletizer removed - infinite source handled by engine.
    """

    stations = [
        Station("Filler", batch_in=1, output_type=MaterialType.TUBE),
        Station("Inspector", batch_in=1, output_type=MaterialType.NONE),
        Station("Packer", batch_in=12, output_type=MaterialType.CASE),
        Station("Palletizer", batch_in=60, output_type=MaterialType.PALLET),
    ]
```

### 3. config.py - Scenario Configuration (NEW)

```python
"""Scenario configuration schemas for what-if experiments."""

from typing import Dict, Optional
from pydantic import BaseModel

from simpy_demo.models import ReliabilityParams, PerformanceParams, QualityParams


class EquipmentParams(BaseModel):
    """Parameters that can vary per scenario (sparse overrides).

    All fields are optional - only specify what you want to override.
    """
    uph: Optional[int] = None
    buffer_capacity: Optional[int] = None
    reliability: Optional[ReliabilityParams] = None
    performance: Optional[PerformanceParams] = None
    quality: Optional[QualityParams] = None


class ScenarioConfig(BaseModel):
    """A scenario = run parameters + equipment parameter overrides.

    Example:
        scenario = ScenarioConfig(
            name="large_buffer_test",
            equipment={
                "Filler": EquipmentParams(buffer_capacity=500)
            }
        )
    """
    name: str
    duration_hours: float = 8.0
    random_seed: Optional[int] = 42
    equipment: Dict[str, EquipmentParams] = {}  # Overrides by station name
```

### 4. baseline.py - Default Parameter Values (NEW)

```python
"""Baseline equipment parameters for the cosmetics line."""

from simpy_demo.config import EquipmentParams
from simpy_demo.models import ReliabilityParams, PerformanceParams, QualityParams


BASELINE: dict[str, EquipmentParams] = {
    "Filler": EquipmentParams(
        uph=10000,
        buffer_capacity=50,
        reliability=ReliabilityParams(mtbf_min=120, mttr_min=15),
        performance=PerformanceParams(jam_prob=0.01, jam_time_sec=15),
        quality=QualityParams(defect_rate=0.02),
    ),
    "Inspector": EquipmentParams(
        uph=11000,
        buffer_capacity=20,
        quality=QualityParams(detection_prob=0.95),
    ),
    "Packer": EquipmentParams(
        uph=12000,
        buffer_capacity=100,
        reliability=ReliabilityParams(mtbf_min=240),
        performance=PerformanceParams(jam_prob=0.05, jam_time_sec=30),
    ),
    "Palletizer": EquipmentParams(
        uph=13000,
        buffer_capacity=40,
        reliability=ReliabilityParams(mtbf_min=480),
    ),
}
```

### 5. equipment.py - Rename and Update Config Access

Rename class `SmartEquipment` -> `Equipment`. Update config access patterns:

```python
# BEFORE:
if self.cfg.mtbf_min:
    p_fail = 1.0 - 2.718 ** -(self.cfg.cycle_time_sec / (self.cfg.mtbf_min * 60))

# AFTER:
if self.cfg.reliability.mtbf_min:
    p_fail = 1.0 - 2.718 ** -(self.cfg.cycle_time_sec / (self.cfg.reliability.mtbf_min * 60))
```

**Full mapping:**
| Before | After |
|--------|-------|
| `self.cfg.mtbf_min` | `self.cfg.reliability.mtbf_min` |
| `self.cfg.mttr_min` | `self.cfg.reliability.mttr_min` |
| `self.cfg.jam_prob` | `self.cfg.performance.jam_prob` |
| `self.cfg.jam_time_sec` | `self.cfg.performance.jam_time_sec` |
| `self.cfg.defect_rate` | `self.cfg.quality.defect_rate` |
| `self.cfg.detection_prob` | `self.cfg.quality.detection_prob` |

### 6. engine.py - Renamed from simulation.py

Rename `ProductionLine` -> `SimulationEngine`. Update to accept topology + baseline + scenario:

```python
"""SimPy simulation engine for production line digital twin."""

import random
from typing import Dict, Tuple

import pandas as pd
import simpy

from simpy_demo.models import MachineConfig, MaterialType, Product, ReliabilityParams, PerformanceParams, QualityParams
from simpy_demo.equipment import Equipment
from simpy_demo.topology import CosmeticsLine, Station
from simpy_demo.config import ScenarioConfig, EquipmentParams


class SimulationEngine:
    """Simulation engine that combines topology + baseline + scenario."""

    def __init__(
        self,
        topology: CosmeticsLine,
        baseline: Dict[str, EquipmentParams],
    ):
        self.topology = topology
        self.baseline = baseline

    def run(self, scenario: ScenarioConfig) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Run scenario and return (telemetry_df, events_df)."""
        # 1. Set random seed
        if scenario.random_seed is not None:
            random.seed(scenario.random_seed)

        # 2. Create SimPy environment
        env = simpy.Environment()

        # 3. Build machine configs by merging baseline + scenario overrides
        machine_configs = self._build_configs(scenario)

        # 4. Build production line
        machines, buffers, reject_bin = self._build_layout(env, machine_configs)

        # 5. Start monitoring
        telemetry_data = []
        env.process(self._monitor_process(env, machines, buffers, telemetry_data))

        # 6. Run simulation
        duration_sec = scenario.duration_hours * 3600
        env.run(until=duration_sec)

        # 7. Compile results
        return self._compile_results(machines, telemetry_data)

    def _build_configs(self, scenario: ScenarioConfig) -> list[MachineConfig]:
        """Merge topology + baseline + scenario into MachineConfigs."""
        configs = []
        for station in self.topology.stations:
            # Start with baseline (or empty if not defined)
            base = self.baseline.get(station.name, EquipmentParams())
            override = scenario.equipment.get(station.name, EquipmentParams())

            # Merge: override wins over baseline
            config = MachineConfig(
                name=station.name,
                uph=override.uph or base.uph or 10000,
                batch_in=station.batch_in,
                output_type=station.output_type,
                buffer_capacity=override.buffer_capacity or base.buffer_capacity or 50,
                reliability=self._merge_params(base.reliability, override.reliability, ReliabilityParams),
                performance=self._merge_params(base.performance, override.performance, PerformanceParams),
                quality=self._merge_params(base.quality, override.quality, QualityParams),
            )
            configs.append(config)
        return configs

    def _merge_params(self, base, override, param_class):
        """Merge two param objects, override wins for non-None fields."""
        if base is None and override is None:
            return param_class()
        if base is None:
            return override
        if override is None:
            return base
        # Field-level merge
        merged = {}
        for field in param_class.model_fields:
            override_val = getattr(override, field, None)
            base_val = getattr(base, field, None)
            merged[field] = override_val if override_val is not None else base_val
        return param_class(**merged)

    def _build_layout(self, env, configs):
        """Build SimPy stores and Equipment instances."""
        # ... (similar to current ProductionLine._build_layout)
        pass

    def _monitor_process(self, env, machines, buffers, telemetry_data):
        """Capture telemetry at 1-second intervals."""
        # ... (similar to current ProductionLine._monitor_process)
        pass

    def _compile_results(self, machines, telemetry_data):
        """Compile DataFrames from simulation data."""
        # ... (similar to current ProductionLine._compile_results)
        pass
```

### 7. run.py - Entry Point (NEW)

```python
"""Entry point for running simulations."""

from simpy_demo.topology import CosmeticsLine
from simpy_demo.baseline import BASELINE
from simpy_demo.config import ScenarioConfig, EquipmentParams
from simpy_demo.engine import SimulationEngine
from simpy_demo.models import ReliabilityParams


def main():
    """Run a sample simulation."""
    # Define a scenario (just the overrides from baseline)
    scenario = ScenarioConfig(
        name="large_buffer_test",
        duration_hours=8.0,
        equipment={
            "Filler": EquipmentParams(buffer_capacity=500)
        }
    )

    # Create engine and run
    engine = SimulationEngine(CosmeticsLine(), BASELINE)
    df_ts, df_ev = engine.run(scenario)

    # Print results
    print(f"\n=== Scenario: {scenario.name} ===")
    print(f"Telemetry rows: {len(df_ts)}")
    print(f"Event rows: {len(df_ev)}")

    # OEE calculation from events...
    # (migrate from scenarios.py)


if __name__ == "__main__":
    main()
```

### 8. __main__.py - Update Entry Point

```python
"""Package entry point: python -m simpy_demo"""

from simpy_demo.run import main

if __name__ == "__main__":
    main()
```

---

## Implementation Steps (Ordered)

### Phase 1: Create new files
1. Create `topology.py` with `Station` and `CosmeticsLine`
2. Create `config.py` with `EquipmentParams` and `ScenarioConfig`
3. Create `baseline.py` with `BASELINE` dict

### Phase 2: Update models.py
1. Add `ReliabilityParams`, `PerformanceParams`, `QualityParams`
2. Update `MachineConfig` to use grouped params
3. Keep `Product`, `MaterialType` unchanged

### Phase 3: Update equipment.py
1. Rename `SmartEquipment` -> `Equipment`
2. Update all config access from flat to grouped (see mapping table)

### Phase 4: Create engine.py
1. Rename `simulation.py` -> `engine.py`
2. Rename `ProductionLine` -> `SimulationEngine`
3. Update constructor to accept `topology` + `baseline`
4. Add `_build_configs()` merge logic
5. Update `run()` to accept `ScenarioConfig`

### Phase 5: Create run.py
1. Create entry point with example usage
2. Migrate OEE calculation from `scenarios.py`

### Phase 6: Update entry points
1. Update `__main__.py` to use `run.main()`
2. Update `__init__.py` exports

### Phase 7: Cleanup
1. Delete `scenarios.py`
2. Update `CLAUDE.md` with new architecture
3. Update `README.md`

---

## Files to Delete
- `src/simpy_demo/scenarios.py`

## Files to Create
- `src/simpy_demo/topology.py`
- `src/simpy_demo/config.py`
- `src/simpy_demo/baseline.py`
- `src/simpy_demo/run.py`

## Files to Update
- `src/simpy_demo/models.py` (add grouped params)
- `src/simpy_demo/equipment.py` (rename class, update config access)
- `src/simpy_demo/simulation.py` -> `engine.py` (rename file and class)
- `src/simpy_demo/__init__.py` (update exports)
- `src/simpy_demo/__main__.py` (update entry point)
- `CLAUDE.md` (update architecture docs)
- `README.md` (update docs)

---

## Future Extensibility: ProductSpec with Economics

Design for later: products that affect equipment behavior and enable economic simulation.

### Future ProductSpec Model

```python
class ProductSpec(BaseModel):
    """Product specification with OEE impact and economics."""
    # Identity
    name: str
    sku: str
    material_type: MaterialType

    # OEE impact modifiers (multiplicative on equipment base params)
    jam_prob_multiplier: float = 1.0       # Some products jam more
    defect_rate_multiplier: float = 1.0    # Tighter tolerances = more defects
    cycle_time_multiplier: float = 1.0     # Complex products run slower
    breakdown_multiplier: float = 1.0      # Abrasive products wear equipment

    # Economics (per unit)
    material_cost: float = 0.0             # Raw material cost
    conversion_cost: float = 0.0           # Labor + energy + overhead
    selling_price: float = 0.0             # Revenue per unit

    @property
    def unit_margin(self) -> float:
        return self.selling_price - self.material_cost - self.conversion_cost
```

### Future Output Table

```
| timestamp | machine | state | sku | units | good | scrap | material_cost | conversion_cost | revenue | margin |
```

### Extension Points (Add to Equipment)

```python
def _get_effective_jam_prob(self, product=None) -> float:
    """Extension point for product modifiers."""
    base = self.cfg.performance.jam_prob
    # Future: if product and product.spec: base *= product.spec.jam_prob_multiplier
    return base
```

### What This Enables

- Value process improvements: "Reducing jams by 20% = $X/shift"
- Product mix optimization: "Product A at 3x margin vs Product B"
- Capital investment ROI: "$100K faster packer -> $Y/year profit"
- Scenario comparison: "What-if product C causes 50% more defects?"

---

## Key Design Decisions

1. **Remove Depalletizer**: It's redundant - infinite source handled by engine
2. **Flat file structure**: No deep twin/assets/behaviors/ hierarchy
3. **Emergent behavior**: Equipment uses generic 6-phase cycle, config determines behavior
4. **Grouped config params**: ReliabilityParams, PerformanceParams, QualityParams for clarity
5. **Baseline + Override pattern**: Define defaults once, scenarios only specify changes
6. **Clean rewrite**: Build new structure, then delete old files
