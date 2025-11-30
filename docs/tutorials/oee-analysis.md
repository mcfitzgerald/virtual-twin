# Tutorial: OEE Analysis

Learn how to calculate Overall Equipment Effectiveness (OEE) from simulation event logs.

## Goal

Calculate OEE for each machine from the events DataFrame and identify improvement opportunities.

## OEE Formula Review

$$
\text{OEE} = \text{Availability} \times \text{Performance} \times \text{Quality}
$$

| Component | Formula | Measures |
|-----------|---------|----------|
| Availability | Uptime / Scheduled Time | Breakdown losses |
| Performance | Actual Output / Theoretical Output | Speed losses |
| Quality | Good Output / Total Output | Quality losses |

## Step 1: Run a Simulation

```bash
poetry run python -m virtual_twin --run baseline_8hr --export
```

## Step 2: Load the Events Data

```python
import pandas as pd

# Load events
events_file = "output/events_baseline_8hr_20250106_060000.csv"
df = pd.read_csv(events_file)

print(f"Total events: {len(df)}")
print(f"Machines: {df['machine'].unique()}")
print(f"States: {df['state'].unique()}")
```

### Output

```
Total events: 15234
Machines: ['Filler' 'Inspector' 'Packer' 'Palletizer']
States: ['STARVED' 'EXECUTE' 'DOWN' 'JAMMED' 'BLOCKED']
```

## Step 3: Calculate Time in Each State

```python
def calculate_state_time(df, machine_name):
    """Calculate total time spent in each state for a machine."""
    machine_df = df[df["machine"] == machine_name].copy()

    # Group by state and sum duration
    state_time = machine_df.groupby("state")["duration"].sum()

    return state_time

# Calculate for Filler
filler_states = calculate_state_time(df, "Filler")
print("Filler state times (seconds):")
print(filler_states)
```

### Output

```
Filler state times (seconds):
state
BLOCKED       450.2
DOWN         2156.8
EXECUTE     24892.1
JAMMED        345.6
STARVED       955.3
Name: duration, dtype: float64
```

## Step 4: Calculate Availability

Availability measures uptime vs. scheduled time.

```python
def calculate_availability(state_time, total_time):
    """
    Availability = (Total Time - Downtime) / Total Time

    Downtime includes:
    - DOWN (breakdowns)
    """
    downtime = state_time.get("DOWN", 0)
    availability = (total_time - downtime) / total_time
    return availability

TOTAL_TIME = 28800  # 8 hours in seconds

filler_availability = calculate_availability(filler_states, TOTAL_TIME)
print(f"Filler Availability: {filler_availability:.1%}")
```

### Output

```
Filler Availability: 92.5%
```

## Step 5: Calculate Performance

Performance measures actual speed vs. theoretical speed.

```python
def calculate_performance(state_time, total_time):
    """
    Performance = Run Time / (Scheduled Time - Downtime - External Losses)

    Run Time = EXECUTE state
    External Losses = STARVED + BLOCKED (not the machine's fault)
    """
    run_time = state_time.get("EXECUTE", 0)
    downtime = state_time.get("DOWN", 0)
    starved = state_time.get("STARVED", 0)
    blocked = state_time.get("BLOCKED", 0)
    jammed = state_time.get("JAMMED", 0)

    # Net operating time (excluding external losses)
    net_time = total_time - downtime - starved - blocked

    if net_time <= 0:
        return 0

    # Performance = actual productive time / available time
    performance = run_time / (run_time + jammed)
    return performance

filler_performance = calculate_performance(filler_states, TOTAL_TIME)
print(f"Filler Performance: {filler_performance:.1%}")
```

### Output

```
Filler Performance: 98.6%
```

## Step 6: Calculate Quality

Quality measures good output vs. total output.

```python
# Load telemetry for quality data
telemetry_file = "output/telemetry_baseline_8hr_20250106_060000.csv"
df_telem = pd.read_csv(telemetry_file)

def calculate_quality(df_telem):
    """
    Quality = Good Output / Total Output
    """
    total_pallets = df_telem["pallets_produced"].sum()
    good_pallets = df_telem["good_pallets"].sum()

    if total_pallets <= 0:
        return 1.0

    quality = good_pallets / total_pallets
    return quality

quality = calculate_quality(df_telem)
print(f"Line Quality: {quality:.1%}")
```

### Output

```
Line Quality: 96.9%
```

## Step 7: Calculate OEE

```python
def calculate_oee(availability, performance, quality):
    """Calculate Overall Equipment Effectiveness."""
    oee = availability * performance * quality
    return oee

filler_oee = calculate_oee(filler_availability, filler_performance, quality)
print(f"\n=== Filler OEE ===")
print(f"Availability: {filler_availability:.1%}")
print(f"Performance:  {filler_performance:.1%}")
print(f"Quality:      {quality:.1%}")
print(f"OEE:          {filler_oee:.1%}")
```

### Output

```
=== Filler OEE ===
Availability: 92.5%
Performance:  98.6%
Quality:      96.9%
OEE:          88.4%
```

## Step 8: Calculate OEE for All Machines

```python
def full_oee_analysis(events_df, telemetry_df, total_time):
    """Calculate OEE for all machines."""
    machines = events_df["machine"].unique()
    quality = calculate_quality(telemetry_df)

    results = []
    for machine in machines:
        state_time = calculate_state_time(events_df, machine)
        availability = calculate_availability(state_time, total_time)
        performance = calculate_performance(state_time, total_time)
        oee = calculate_oee(availability, performance, quality)

        results.append({
            "machine": machine,
            "availability": availability * 100,
            "performance": performance * 100,
            "quality": quality * 100,
            "oee": oee * 100,
            "down_time": state_time.get("DOWN", 0),
            "jam_time": state_time.get("JAMMED", 0),
        })

    return pd.DataFrame(results)

oee_results = full_oee_analysis(df, df_telem, TOTAL_TIME)
print("\n=== OEE by Machine ===\n")
print(oee_results.to_string(index=False))
```

### Output

```
=== OEE by Machine ===

    machine  availability  performance  quality    oee  down_time  jam_time
     Filler          92.5         98.6     96.9   88.4     2156.8     345.6
  Inspector          99.2         99.8     96.9   95.9      230.4      45.2
     Packer          94.8         97.2     96.9   89.3     1497.6     678.4
 Palletizer          97.5         99.1     96.9   93.6      720.0     234.5
```

## Step 9: Identify Improvement Opportunities

```python
# Find biggest losses
print("\n=== Loss Analysis ===\n")

# Availability losses (downtime)
print("Availability Losses (Down Time):")
down_sorted = oee_results.sort_values("down_time", ascending=False)
for _, row in down_sorted.iterrows():
    hours = row["down_time"] / 3600
    print(f"  {row['machine']}: {hours:.2f} hours ({row['availability']:.1f}% availability)")

# Performance losses (jams)
print("\nPerformance Losses (Jam Time):")
jam_sorted = oee_results.sort_values("jam_time", ascending=False)
for _, row in jam_sorted.iterrows():
    minutes = row["jam_time"] / 60
    print(f"  {row['machine']}: {minutes:.1f} minutes ({row['performance']:.1f}% performance)")
```

### Output

```
=== Loss Analysis ===

Availability Losses (Down Time):
  Filler: 0.60 hours (92.5% availability)
  Packer: 0.42 hours (94.8% availability)
  Palletizer: 0.20 hours (97.5% availability)
  Inspector: 0.06 hours (99.2% availability)

Performance Losses (Jam Time):
  Packer: 11.3 minutes (97.2% performance)
  Filler: 5.8 minutes (98.6% performance)
  Palletizer: 3.9 minutes (99.1% performance)
  Inspector: 0.8 minutes (99.8% performance)
```

**Insight**: Filler has the most availability loss; Packer has the most performance loss.

## Step 10: Visualize OEE Waterfall

```python
import matplotlib.pyplot as plt

# OEE waterfall for Filler
fig, ax = plt.subplots(figsize=(10, 6))

machine = "Filler"
row = oee_results[oee_results["machine"] == machine].iloc[0]

categories = ["Availability", "Performance", "Quality", "OEE"]
values = [row["availability"], row["performance"], row["quality"], row["oee"]]
colors = ["#2196F3", "#4CAF50", "#FF9800", "#9C27B0"]

bars = ax.bar(categories, values, color=colors)
ax.set_ylabel("Percentage")
ax.set_title(f"{machine} OEE Breakdown")
ax.set_ylim(0, 105)

# Add value labels
for bar, val in zip(bars, values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
            f"{val:.1f}%", ha="center")

plt.savefig("oee_waterfall.png")
print("Saved: oee_waterfall.png")
```

## Complete OEE Analysis Script

```python
# oee_analysis.py
import pandas as pd
import sys

def analyze_oee(events_file, telemetry_file):
    """Complete OEE analysis from simulation outputs."""

    # Load data
    events = pd.read_csv(events_file)
    telemetry = pd.read_csv(telemetry_file)

    # Total simulation time
    total_time = telemetry["time"].max()

    # Calculate quality (line-level)
    total_pallets = telemetry["pallets_produced"].sum()
    good_pallets = telemetry["good_pallets"].sum()
    quality = good_pallets / total_pallets if total_pallets > 0 else 1.0

    # Calculate per-machine metrics
    results = []
    for machine in events["machine"].unique():
        machine_events = events[events["machine"] == machine]
        state_time = machine_events.groupby("state")["duration"].sum()

        # Availability
        downtime = state_time.get("DOWN", 0)
        availability = (total_time - downtime) / total_time

        # Performance
        run_time = state_time.get("EXECUTE", 0)
        jam_time = state_time.get("JAMMED", 0)
        performance = run_time / (run_time + jam_time) if (run_time + jam_time) > 0 else 1.0

        # OEE
        oee = availability * performance * quality

        results.append({
            "Machine": machine,
            "Availability": f"{availability*100:.1f}%",
            "Performance": f"{performance*100:.1f}%",
            "Quality": f"{quality*100:.1f}%",
            "OEE": f"{oee*100:.1f}%",
        })

    return pd.DataFrame(results)

if __name__ == "__main__":
    events_file = sys.argv[1] if len(sys.argv) > 1 else "output/events_baseline_8hr_*.csv"
    telemetry_file = sys.argv[2] if len(sys.argv) > 2 else "output/telemetry_baseline_8hr_*.csv"

    import glob
    events_file = glob.glob(events_file)[0]
    telemetry_file = glob.glob(telemetry_file)[0]

    results = analyze_oee(events_file, telemetry_file)
    print("\n=== OEE Analysis ===\n")
    print(results.to_string(index=False))
```

Usage:

```bash
python oee_analysis.py
```

## What You Learned

1. OEE components: Availability, Performance, Quality
2. Calculating state time from events
3. OEE formula implementation
4. Identifying loss categories and improvement opportunities
5. Visualizing OEE breakdowns

## Next Steps

- **[Concepts: OEE](../getting-started/concepts.md#oee-overall-equipment-effectiveness)** - OEE fundamentals
- **[Outputs Reference](../user-guide/outputs.md)** - Event log details
- **[Custom Equipment Tutorial](custom-equipment.md)** - Improve equipment parameters
