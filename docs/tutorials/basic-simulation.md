# Tutorial: Basic Simulation

A complete walkthrough of running your first simulation and understanding the results.

## Prerequisites

- SimPy-Demo installed ([Installation Guide](../getting-started/installation.md))
- Terminal access

## Step 1: Explore the Configuration

First, let's understand what we're about to run.

### View the Run Config

```bash
cat config/runs/baseline_8hr.yaml
```

```yaml
name: baseline_8hr
scenario: baseline
product: fresh_toothpaste_5oz
duration_hours: 8.0
random_seed: 42
telemetry_interval_sec: 300.0
start_time: "2025-01-06T06:00:00"
```

This tells us:

- We'll run the `baseline` scenario
- With `fresh_toothpaste_5oz` product (enables economics)
- For 8 hours
- Starting at 6:00 AM
- Capturing data every 5 minutes (300 seconds)

### View the Scenario Config

```bash
cat config/scenarios/baseline.yaml
```

```yaml
name: baseline
topology: cosmetics_line
equipment:
  - Filler
  - Inspector
  - Packer
  - Palletizer
```

### View the Topology

```bash
cat config/topologies/cosmetics_line.yaml
```

```yaml
name: cosmetics_line
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

This is a linear cosmetics packaging line:

```
Filler → Inspector → Packer → Palletizer
(tubes)   (tubes)    (cases)   (pallets)
```

## Step 2: Run the Simulation

```bash
poetry run python -m simpy_demo --run baseline_8hr --export
```

### Expected Output

```
=== Configuration ===
Run: baseline_8hr
Scenario: baseline
Topology: cosmetics_line (4 stations)
Product: fresh_toothpaste_5oz
Duration: 8.0 hours

=== Simulation Running ===
Simulation time: 0.0s / 28800.0s
Simulation time: 7200.0s / 28800.0s (25%)
Simulation time: 14400.0s / 28800.0s (50%)
Simulation time: 21600.0s / 28800.0s (75%)
Simulation time: 28800.0s / 28800.0s (100%)

=== Simulation Complete ===
Duration: 8.0 hours (28800.0 seconds)

Production:
  Tubes produced: 27,648
  Cases produced: 2,304
  Pallets produced: 384
  Good pallets: 372
  Defective pallets: 12

Economics:
  Material cost: $57,600.00
  Conversion cost: $12,800.00
  Revenue: $167,400.00
  Gross margin: $97,000.00 (57.9%)

OEE by Machine:
  Filler: 92.3%
  Inspector: 98.1%
  Packer: 94.5%
  Palletizer: 96.8%

Results exported to: output/
```

## Step 3: Explore the Output Files

```bash
ls output/
```

```
telemetry_baseline_8hr_20250106_060000.csv
events_baseline_8hr_20250106_060000.csv
```

### View Telemetry Data

```bash
head -5 output/telemetry_baseline_8hr_20250106_060000.csv
```

```csv
time,datetime,sku_name,tubes_produced,cases_produced,pallets_produced,Buf_Filler,Filler_state
300.0,2025-01-06T06:05:00,fresh_toothpaste_5oz,333,27,0,45,EXECUTE
600.0,2025-01-06T06:10:00,fresh_toothpaste_5oz,334,28,0,52,EXECUTE
900.0,2025-01-06T06:15:00,fresh_toothpaste_5oz,330,27,0,38,EXECUTE
1200.0,2025-01-06T06:20:00,fresh_toothpaste_5oz,331,27,0,41,EXECUTE
```

### View Events Data

```bash
head -10 output/events_baseline_8hr_20250106_060000.csv
```

```csv
datetime,timestamp,machine,state,event_type,duration
2025-01-06T06:00:00,0.0,Filler,STARVED,start,0.0
2025-01-06T06:00:00.1,0.1,Filler,EXECUTE,collected,0.1
2025-01-06T06:00:03.7,3.7,Filler,STARVED,produced,3.6
2025-01-06T06:00:03.8,3.8,Filler,EXECUTE,collected,0.1
```

## Step 4: Analyze Results with Python

Create a simple analysis script:

```python
# analyze.py
import pandas as pd

# Load telemetry
df = pd.read_csv("output/telemetry_baseline_8hr_20250106_060000.csv")

print("=== Production Summary ===")
print(f"Total tubes: {df['tubes_produced'].sum():,}")
print(f"Total cases: {df['cases_produced'].sum():,}")
print(f"Total pallets: {df['pallets_produced'].sum():,}")

print("\n=== Economic Summary ===")
print(f"Total revenue: ${df['revenue'].sum():,.2f}")
print(f"Total margin: ${df['gross_margin'].sum():,.2f}")

print("\n=== Buffer Statistics ===")
print(f"Filler buffer - mean: {df['Buf_Filler'].mean():.1f}, max: {df['Buf_Filler'].max()}")

print("\n=== Production by Hour ===")
df['hour'] = df['time'] // 3600
hourly = df.groupby('hour')['pallets_produced'].sum()
print(hourly)
```

Run it:

```bash
python analyze.py
```

## Step 5: Visualize Results

```python
# visualize.py
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("output/telemetry_baseline_8hr_20250106_060000.csv")
df['datetime'] = pd.to_datetime(df['datetime'])

fig, axes = plt.subplots(2, 2, figsize=(12, 8))

# Production over time
df['cumulative_pallets'] = df['pallets_produced'].cumsum()
axes[0, 0].plot(df['datetime'], df['cumulative_pallets'])
axes[0, 0].set_title('Cumulative Pallet Production')
axes[0, 0].set_ylabel('Pallets')

# Buffer levels
axes[0, 1].plot(df['datetime'], df['Buf_Filler'], label='Filler')
axes[0, 1].plot(df['datetime'], df['Buf_Packer'], label='Packer')
axes[0, 1].set_title('Buffer Levels')
axes[0, 1].legend()

# Cumulative margin
df['cumulative_margin'] = df['gross_margin'].cumsum()
axes[1, 0].plot(df['datetime'], df['cumulative_margin'])
axes[1, 0].set_title('Cumulative Gross Margin')
axes[1, 0].set_ylabel('$')

# Production rate
axes[1, 1].bar(df['datetime'], df['pallets_produced'])
axes[1, 1].set_title('Pallets per Interval')

plt.tight_layout()
plt.savefig('simulation_results.png')
print("Saved: simulation_results.png")
```

## Step 6: Try a Different Seed

Run with a different random seed to see variation:

```bash
# Modify seed temporarily
poetry run python -c "
from simpy_demo import SimulationEngine

engine = SimulationEngine('config')
df_ts, df_ev = engine.run('baseline_8hr')

# Manually run with different seed
import random
random.seed(123)  # Different seed

df_ts2, df_ev2 = engine.run('baseline_8hr')

print(f'Seed 42 pallets: {df_ts[\"pallets_produced\"].sum()}')
print(f'Seed 123 pallets: {df_ts2[\"pallets_produced\"].sum()}')
"
```

## What You Learned

1. **Configuration structure**: Run → Scenario → Topology → Equipment
2. **Running simulations**: `poetry run python -m simpy_demo --run NAME --export`
3. **Output files**: Telemetry (time-series) and Events (state log)
4. **Data analysis**: Loading and analyzing CSV outputs

## Next Steps

- **[Custom Equipment Tutorial](custom-equipment.md)** - Create your own equipment config
- **[Buffer Optimization Tutorial](buffer-optimization.md)** - Experiment with buffer sizes
- **[Configuration Guide](../user-guide/configuration.md)** - Deep dive into config options
