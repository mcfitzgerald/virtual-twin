# Outputs

SimPy-Demo produces three types of output: telemetry time-series, event logs, and summary statistics.

## Output Files

### Direct Run (`--export`)

```
output/
├── telemetry_baseline_8hr_20250129_060000.csv
└── events_baseline_8hr_20250129_060000.csv
```

### Scenario Bundle (`simulate`)

```
scenarios/baseline_8hr_20250129_143022/output/
├── telemetry.csv
├── events.csv
└── summary.json
```

## Telemetry DataFrame

Time-series data captured at configurable intervals (default: 5 minutes / 300 seconds).

### Key Characteristics

- **Incremental values**: Production counts, economics are per-interval deltas, not cumulative
- **Snapshot values**: Buffer levels, machine states are point-in-time values
- **SKU context**: Product info included when product is configured

### Columns

#### Time Columns

| Column | Type | Description |
|--------|------|-------------|
| `time` | float | Simulation time in seconds |
| `datetime` | string | ISO 8601 timestamp |

#### SKU Context (if product configured)

| Column | Type | Description |
|--------|------|-------------|
| `sku_name` | string | Product name |
| `sku_description` | string | Product description |
| `size_oz` | float | Product size |
| `units_per_case` | int | Units per case |
| `cases_per_pallet` | int | Cases per pallet |

#### Production (incremental)

| Column | Type | Description |
|--------|------|-------------|
| `tubes_produced` | int | Tubes produced this interval |
| `cases_produced` | int | Cases produced this interval |
| `pallets_produced` | int | Pallets produced this interval |
| `good_pallets` | int | Good pallets this interval |
| `defective_pallets` | int | Defective pallets this interval |

#### Quality (incremental)

| Column | Type | Description |
|--------|------|-------------|
| `defects_created` | int | Defects created this interval |
| `defects_detected` | int | Defects detected this interval |

#### Economics (incremental, if product configured)

| Column | Type | Description |
|--------|------|-------------|
| `material_cost` | float | Material cost this interval ($) |
| `conversion_cost` | float | Conversion cost this interval ($) |
| `revenue` | float | Revenue this interval ($) |
| `gross_margin` | float | Gross margin this interval ($) |

#### Buffer Levels (snapshot)

| Column | Type | Description |
|--------|------|-------------|
| `Buf_Filler` | int | Filler output buffer level |
| `Buf_Inspector` | int | Inspector output buffer level |
| `Buf_Packer` | int | Packer output buffer level |
| `Buf_Palletizer` | int | Palletizer output buffer level |

#### Machine States (snapshot)

| Column | Type | Description |
|--------|------|-------------|
| `Filler_state` | string | Current state: STARVED, EXECUTE, DOWN, JAMMED, BLOCKED |
| `Inspector_state` | string | Current state |
| `Packer_state` | string | Current state |
| `Palletizer_state` | string | Current state |

### Example Data

```csv
time,datetime,tubes_produced,cases_produced,pallets_produced,Buf_Filler,Filler_state
300.0,2025-01-29T06:05:00,333,27,0,45,EXECUTE
600.0,2025-01-29T06:10:00,334,28,0,52,EXECUTE
900.0,2025-01-29T06:15:00,330,27,0,38,EXECUTE
1200.0,2025-01-29T06:20:00,0,0,0,12,DOWN
1500.0,2025-01-29T06:25:00,320,26,1,67,EXECUTE
```

### Working with Telemetry

```python
import pandas as pd

df = pd.read_csv("output/telemetry_baseline_8hr_*.csv")

# Total production (sum incremental values)
total_pallets = df["pallets_produced"].sum()
total_revenue = df["revenue"].sum()

# Time-series analysis
df["datetime"] = pd.to_datetime(df["datetime"])
df.set_index("datetime", inplace=True)

# Plot buffer levels over time
df["Buf_Filler"].plot(title="Filler Buffer Level")

# Detect downtime periods
downtime = df[df["Filler_state"] == "DOWN"]
```

## Events DataFrame

State transition log capturing every state change for every machine.

### Columns

| Column | Type | Description |
|--------|------|-------------|
| `datetime` | string | ISO 8601 timestamp |
| `timestamp` | float | Simulation time in seconds |
| `machine` | string | Equipment name |
| `state` | string | New state |
| `event_type` | string | State transition identifier |
| `duration` | float | Time spent in previous state (seconds) |

### Machine States

| State | Description |
|-------|-------------|
| `STARVED` | Waiting for input from upstream buffer |
| `EXECUTE` | Actively processing (value-add time) |
| `DOWN` | Broken down, undergoing repair |
| `JAMMED` | Experiencing micro-stop/jam |
| `BLOCKED` | Waiting to output (downstream buffer full) |

### Example Data

```csv
datetime,timestamp,machine,state,event_type,duration
2025-01-29T06:00:00,0.0,Filler,STARVED,start,0.0
2025-01-29T06:00:00.1,0.1,Filler,EXECUTE,collected,0.1
2025-01-29T06:00:03.7,3.7,Filler,STARVED,produced,3.6
2025-01-29T06:00:03.8,3.8,Filler,EXECUTE,collected,0.1
2025-01-29T06:15:42.3,942.3,Filler,DOWN,breakdown,938.5
2025-01-29T06:18:12.3,1092.3,Filler,STARVED,repaired,150.0
```

### Calculating OEE from Events

```python
import pandas as pd

df = pd.read_csv("output/events_baseline_8hr_*.csv")

# Filter to one machine
filler = df[df["machine"] == "Filler"]

# Calculate time in each state
state_time = filler.groupby("state")["duration"].sum()

# Total simulation time
total_time = 28800  # 8 hours in seconds

# Availability = (Total - DOWN) / Total
availability = (total_time - state_time.get("DOWN", 0)) / total_time

# Performance = EXECUTE / (Total - DOWN - STARVED - BLOCKED)
scheduled_time = total_time - state_time.get("DOWN", 0)
run_time = state_time.get("EXECUTE", 0)
performance = run_time / (scheduled_time - state_time.get("JAMMED", 0))

print(f"Filler Availability: {availability:.1%}")
print(f"Filler Performance: {performance:.1%}")
```

## Summary JSON

Generated by the `simulate` command with production totals, economics, and OEE.

### Structure

```json
{
  "run_name": "baseline_8hr",
  "duration_hours": 8.0,
  "production": {
    "tubes_produced": 27648,
    "cases_produced": 2304,
    "pallets_produced": 384,
    "good_pallets": 372,
    "defective_pallets": 12
  },
  "economics": {
    "material_cost": 57600.0,
    "conversion_cost": 12800.0,
    "revenue": 167400.0,
    "gross_margin": 97000.0,
    "margin_percent": 57.94
  },
  "oee": {
    "Filler": 92.3,
    "Inspector": 98.1,
    "Packer": 94.5,
    "Palletizer": 96.8
  }
}
```

### Loading Summary

```python
import json

with open("scenarios/baseline_8hr_*/output/summary.json") as f:
    summary = json.load(f)

print(f"Total revenue: ${summary['economics']['revenue']:,.0f}")
print(f"OEE - Filler: {summary['oee']['Filler']:.1f}%")
```

## Data Analysis Tips

### Detecting Anomalies

```python
# Find intervals with zero production
zero_production = df[df["pallets_produced"] == 0]
print(f"Zero production intervals: {len(zero_production)}")

# Find intervals with downtime
downtime_intervals = df[df["Filler_state"] == "DOWN"]
print(f"Downtime intervals: {len(downtime_intervals)}")
```

### Buffer Analysis

```python
# Buffer statistics
print(df["Buf_Filler"].describe())

# Buffer utilization
capacity = 200
utilization = df["Buf_Filler"].mean() / capacity
print(f"Filler buffer utilization: {utilization:.1%}")
```

### Economic Analysis

```python
# Cost per pallet
total_cost = df["material_cost"].sum() + df["conversion_cost"].sum()
total_pallets = df["pallets_produced"].sum()
cost_per_pallet = total_cost / total_pallets
print(f"Cost per pallet: ${cost_per_pallet:.2f}")

# Margin trend over time
df["margin_cumulative"] = df["gross_margin"].cumsum()
df["margin_cumulative"].plot(title="Cumulative Gross Margin")
```

## Next Steps

- **[OEE Analysis Tutorial](../tutorials/oee-analysis.md)** - Detailed OEE calculation
- **[Buffer Optimization Tutorial](../tutorials/buffer-optimization.md)** - Analyze buffer impact
- **[Config Schema](../reference/config-schema.md)** - Telemetry interval configuration
