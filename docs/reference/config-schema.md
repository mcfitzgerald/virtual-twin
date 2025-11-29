# Config Schema Reference

Complete reference for all YAML configuration fields.

## Run Config

**Location**: `config/runs/*.yaml`

```yaml
name: baseline_8hr
scenario: baseline
product: fresh_toothpaste_5oz
duration_hours: 8.0
random_seed: 42
telemetry_interval_sec: 300.0
start_time: "2025-01-06T06:00:00"
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | Unique identifier for the run |
| `scenario` | string | Yes | - | Reference to scenario config name |
| `product` | string | No | null | Reference to product config name |
| `duration_hours` | float | No | 8.0 | Simulation duration in hours |
| `random_seed` | int | No | 42 | Random seed for reproducibility |
| `telemetry_interval_sec` | float | No | 300.0 | Telemetry capture interval (seconds) |
| `start_time` | string | No | now() | ISO 8601 timestamp for simulation start |

---

## Scenario Config

**Location**: `config/scenarios/*.yaml`

```yaml
name: baseline
topology: cosmetics_line
equipment:
  - Filler
  - Inspector
  - Packer
  - Palletizer
behavior: default_6phase
overrides:
  Filler:
    buffer_capacity: 200
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | Unique identifier for the scenario |
| `topology` | string | Yes | - | Reference to topology config name |
| `equipment` | list[string] | Yes | - | List of equipment config names |
| `behavior` | string | No | default_6phase | Reference to behavior config name |
| `overrides` | dict | No | {} | Per-equipment parameter overrides |

### Overrides

Overrides are keyed by equipment name and can modify any equipment field:

```yaml
overrides:
  Filler:
    uph: 4500
    buffer_capacity: 300
    reliability:
      mtbf_min: 1800
    performance:
      jam_prob: 0.001
```

---

## Topology Config

**Location**: `config/topologies/*.yaml`

### Linear Format

```yaml
name: cosmetics_line
source: infinite_raw
stations:
  - name: Filler
    batch_in: 1
    output_type: Tube
  - name: Inspector
    batch_in: 1
    output_type: Tube
  - name: Packer
    batch_in: 12
    output_type: Case
  - name: Palletizer
    batch_in: 60
    output_type: Pallet
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | Unique identifier |
| `source` | string | No | infinite_raw | Reference to source config |
| `stations` | list | Yes | - | Ordered list of stations |

#### Station Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | Station name (must match equipment name) |
| `batch_in` | int | No | 1 | Number of inputs per cycle |
| `output_type` | string | Yes | - | Output material type: Tube, Case, Pallet |

### Graph Format

```yaml
name: cosmetics_line_graph
nodes:
  - name: Filler
    equipment_ref: filler
    batch_in: 1
    output_type: Tube
  - name: Inspector
    equipment_ref: inspector
    batch_in: 1
    output_type: Tube
edges:
  - source: _source
    target: Filler
  - source: Filler
    target: Inspector
  - source: Inspector
    target: Packer
    condition: "not product.is_defective"
  - source: Inspector
    target: _reject
    condition: "product.is_defective"
```

#### Node Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | Node name |
| `equipment_ref` | string | No | name | Reference to equipment config |
| `batch_in` | int | No | 1 | Number of inputs per cycle |
| `output_type` | string | Yes | - | Output material type |

#### Edge Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `source` | string | Yes | - | Source node name |
| `target` | string | Yes | - | Target node name |
| `capacity` | int | No | null | Buffer capacity override |
| `condition` | string | No | null | Routing condition |

#### Special Nodes

| Node | Description |
|------|-------------|
| `_source` | Infinite raw material source |
| `_sink` | Final output destination |
| `_reject` | Defective product bin |

#### Condition Expressions

| Expression | Meaning |
|------------|---------|
| `product.is_defective` | Product is defective |
| `not product.is_defective` | Product is good |

---

## Equipment Config

**Location**: `config/equipment/*.yaml`

```yaml
name: Filler
uph: 4000
buffer_capacity: 200

reliability:
  mtbf_min: 3600
  mtbf_max: 7200
  mttr_min: 120
  mttr_max: 300

performance:
  jam_prob: 0.002
  jam_time_sec: 30

quality:
  defect_rate: 0.01
  detection_prob: 0.0

cost_rates:
  labor_per_hour: 25.0
  energy_per_hour: 15.0
  overhead_per_hour: 10.0
```

### Top-Level Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | Equipment name |
| `uph` | int | Yes | - | Units per hour |
| `buffer_capacity` | int | No | 100 | Output buffer capacity |

### Reliability Parameters

Controls availability loss (breakdowns).

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `mtbf_min` | float | No | null | Min time between failures (seconds) |
| `mtbf_max` | float | No | null | Max time between failures |
| `mttr_min` | float | No | null | Min repair time (seconds) |
| `mttr_max` | float | No | null | Max repair time |

!!! note
    If `mtbf_min` is null, no breakdowns occur.

### Performance Parameters

Controls performance loss (micro-stops/jams).

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `jam_prob` | float | No | 0.0 | Probability of jam per cycle (0.0-1.0) |
| `jam_time_sec` | float | No | 30.0 | Jam duration (seconds) |

### Quality Parameters

Controls quality loss (defects).

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `defect_rate` | float | No | 0.0 | Probability of defect (0.0-1.0) |
| `detection_prob` | float | No | 0.0 | Probability of detecting defect (0.0-1.0) |

### Cost Rates

Controls conversion cost calculation.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `labor_per_hour` | float | No | 0.0 | Labor cost per hour ($) |
| `energy_per_hour` | float | No | 0.0 | Energy cost per hour ($) |
| `overhead_per_hour` | float | No | 0.0 | Overhead cost per hour ($) |

---

## Product Config

**Location**: `config/products/*.yaml`

```yaml
name: fresh_toothpaste_5oz
description: "Fresh Toothpaste 5oz Tube"
size_oz: 5.0
net_weight_g: 141.75
units_per_case: 12
cases_per_pallet: 60
material_cost: 150.00
selling_price: 450.00
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | Unique identifier |
| `description` | string | No | "" | Human-readable description |
| `size_oz` | float | No | 0.0 | Product size in ounces |
| `net_weight_g` | float | No | 0.0 | Net weight in grams |
| `units_per_case` | int | No | 1 | Number of units per case |
| `cases_per_pallet` | int | No | 1 | Number of cases per pallet |
| `material_cost` | float | No | 0.0 | Material cost per pallet ($) |
| `selling_price` | float | No | 0.0 | Selling price per pallet ($) |

---

## Behavior Config

**Location**: `config/behaviors/*.yaml`

```yaml
name: default_6phase
phases:
  - name: collect
    handler: CollectPhase
    enabled: "always"
  - name: breakdown
    handler: BreakdownPhase
    enabled: "config.reliability.mtbf_min is not None"
  - name: microstop
    handler: MicrostopPhase
    enabled: "config.performance.jam_prob > 0"
  - name: execute
    handler: ExecutePhase
    enabled: "always"
  - name: transform
    handler: TransformPhase
    enabled: "always"
  - name: inspect
    handler: InspectPhase
    enabled: "always"
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | Unique identifier |
| `phases` | list | Yes | - | Ordered list of phases |

### Phase Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Phase name |
| `handler` | string | Yes | Phase class name |
| `enabled` | string | Yes | Enabled condition |

### Available Handlers

| Handler | Description |
|---------|-------------|
| `CollectPhase` | Collect batch_in items from upstream |
| `BreakdownPhase` | Poisson failure check |
| `MicrostopPhase` | Bernoulli jam check |
| `ExecutePhase` | Process for cycle_time_sec |
| `TransformPhase` | Create output product |
| `InspectPhase` | Quality inspection and routing |

### Enabled Conditions

| Condition | Meaning |
|-----------|---------|
| `"always"` | Always enabled |
| `"config.reliability.mtbf_min is not None"` | Enabled if MTBF configured |
| `"config.performance.jam_prob > 0"` | Enabled if jam probability > 0 |

---

## Source Config

**Location**: `config/sources/*.yaml`

```yaml
name: infinite_raw
initial_inventory: 100000
material_type: NONE
parent_machine: Raw
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | Unique identifier |
| `initial_inventory` | int | No | 100000 | Initial items in source |
| `material_type` | string | No | NONE | Material type: TUBE, CASE, PALLET, NONE |
| `parent_machine` | string | No | Raw | Name of parent machine |

---

## Defaults Config

**Location**: `config/defaults.yaml`

```yaml
simulation:
  duration_hours: 8.0
  random_seed: 42
  telemetry_interval_sec: 300.0

equipment:
  buffer_capacity: 100
  uph: 1000

product:
  units_per_case: 12
  cases_per_pallet: 60
```

Provides default values when not specified in individual configs.

---

## Constants Config

**Location**: `config/constants.yaml`

```yaml
SECONDS_PER_HOUR: 3600
TUBE_WEIGHT_G: 141.75
DEFAULT_WAREHOUSE: "Warehouse_A"
```

Named constants for use in expressions and defaults.
