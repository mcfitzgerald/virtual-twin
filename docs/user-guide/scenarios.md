# Scenarios

Scenarios enable what-if experiments by combining topologies with equipment configurations and parameter overrides.

## Scenario Structure

A scenario defines:

1. Which **topology** (line structure) to use
2. Which **equipment** configs to place at each station
3. Optional **overrides** for parameter tuning

```yaml
# config/scenarios/baseline.yaml
name: baseline
topology: cosmetics_line
equipment:
  - Filler
  - Inspector
  - Packer
  - Palletizer
overrides:
  Filler:
    buffer_capacity: 200
```

## Creating What-If Experiments

### Experiment 1: Buffer Size Impact

Test how buffer capacity affects throughput:

```yaml
# config/scenarios/high_buffer.yaml
name: high_buffer
topology: cosmetics_line
equipment:
  - Filler
  - Inspector
  - Packer
  - Palletizer
overrides:
  Filler:
    buffer_capacity: 500
  Inspector:
    buffer_capacity: 500
  Packer:
    buffer_capacity: 500
```

Create a run config:

```yaml
# config/runs/high_buffer_8hr.yaml
name: high_buffer_8hr
scenario: high_buffer
product: fresh_toothpaste_5oz
duration_hours: 8.0
random_seed: 42
```

Run and compare:

```bash
# Baseline
poetry run python -m simpy_demo --run baseline_8hr --export

# High buffer
poetry run python -m simpy_demo --run high_buffer_8hr --export

# Compare outputs
diff output/telemetry_baseline_8hr_*.csv output/telemetry_high_buffer_8hr_*.csv
```

### Experiment 2: Reliability Impact

Test how equipment reliability affects OEE:

```yaml
# config/scenarios/high_reliability.yaml
name: high_reliability
topology: cosmetics_line
equipment:
  - Filler
  - Inspector
  - Packer
  - Palletizer
overrides:
  Filler:
    reliability:
      mtbf_min: 7200    # Double MTBF
      mtbf_max: 14400
      mttr_min: 60      # Halve repair time
      mttr_max: 150
  Packer:
    reliability:
      mtbf_min: 7200
      mtbf_max: 14400
```

### Experiment 3: Speed Increase

Test the impact of increasing line speed:

```yaml
# config/scenarios/high_speed.yaml
name: high_speed
topology: cosmetics_line
equipment:
  - Filler
  - Inspector
  - Packer
  - Palletizer
overrides:
  Filler:
    uph: 4800           # 20% faster
  Inspector:
    uph: 4800
  Packer:
    uph: 4800
  Palletizer:
    uph: 4800
```

### Experiment 4: Quality Improvement

Test the impact of better quality control:

```yaml
# config/scenarios/high_quality.yaml
name: high_quality
topology: cosmetics_line
equipment:
  - Filler
  - Inspector
  - Packer
  - Palletizer
overrides:
  Filler:
    quality:
      defect_rate: 0.005    # Halve defect rate
  Inspector:
    quality:
      detection_prob: 0.99  # Better detection
```

## Override Syntax

### Simple Field Override

```yaml
overrides:
  Filler:
    uph: 4500
    buffer_capacity: 300
```

### Nested Field Override

```yaml
overrides:
  Filler:
    reliability:
      mtbf_min: 1800
      mtbf_max: 3600
    performance:
      jam_prob: 0.001
```

### Partial Nested Override

Only specified fields are changed; others keep their base values:

```yaml
overrides:
  Filler:
    reliability:
      mtbf_min: 1800    # Changed
      # mtbf_max, mttr_min, mttr_max keep base values
```

## Scenario Variations

### Multiple Runs from One Scenario

Create multiple runs with different seeds:

```yaml
# config/runs/baseline_8hr_seed1.yaml
name: baseline_8hr_seed1
scenario: baseline
random_seed: 1

# config/runs/baseline_8hr_seed2.yaml
name: baseline_8hr_seed2
scenario: baseline
random_seed: 2

# config/runs/baseline_8hr_seed3.yaml
name: baseline_8hr_seed3
scenario: baseline
random_seed: 3
```

Run all and analyze variance:

```bash
for seed in 1 2 3; do
  poetry run python -m simpy_demo --run baseline_8hr_seed$seed --export
done
```

### Different Durations

```yaml
# config/runs/baseline_1hr.yaml
name: baseline_1hr
scenario: baseline
duration_hours: 1.0

# config/runs/baseline_24hr.yaml
name: baseline_24hr
scenario: baseline
duration_hours: 24.0
```

## Comparing Scenarios

### Side-by-Side Analysis

```python
import pandas as pd

# Load results
baseline = pd.read_csv("output/telemetry_baseline_8hr_*.csv")
high_buffer = pd.read_csv("output/telemetry_high_buffer_8hr_*.csv")

# Compare total production
print("Baseline pallets:", baseline["pallets_produced"].sum())
print("High buffer pallets:", high_buffer["pallets_produced"].sum())

# Compare economics
print("Baseline margin:", baseline["gross_margin"].sum())
print("High buffer margin:", high_buffer["gross_margin"].sum())
```

### Statistical Analysis

Run multiple seeds and compute statistics:

```python
import pandas as pd
import numpy as np

results = []
for seed in range(1, 11):
    df = pd.read_csv(f"output/telemetry_baseline_8hr_seed{seed}_*.csv")
    results.append({
        "seed": seed,
        "pallets": df["pallets_produced"].sum(),
        "margin": df["gross_margin"].sum()
    })

df_results = pd.DataFrame(results)
print(f"Pallets: {df_results['pallets'].mean():.0f} ± {df_results['pallets'].std():.0f}")
print(f"Margin: ${df_results['margin'].mean():,.0f} ± ${df_results['margin'].std():,.0f}")
```

## Best Practices

### 1. Use Descriptive Names

```yaml
# Good
name: high_buffer_filler_500

# Less clear
name: test_1
```

### 2. Document Changes in Comments

```yaml
# config/scenarios/high_buffer_filler_500.yaml
# Testing impact of 2.5x buffer capacity on Filler
# Hypothesis: Reduces starvation at Inspector, increases throughput
name: high_buffer_filler_500
topology: cosmetics_line
equipment:
  - Filler
  - Inspector
  - Packer
  - Palletizer
overrides:
  Filler:
    buffer_capacity: 500  # Baseline: 200
```

### 3. Keep Baseline as Reference

Always compare against a known baseline scenario.

### 4. Change One Variable at a Time

For clear cause-effect analysis, modify one parameter per experiment.

### 5. Use Scenario Bundles for Production

Use `configure` + `simulate` for experiments you want to reproduce:

```bash
# Generate bundle with frozen config
poetry run python -m simpy_demo configure --run high_buffer_8hr

# Run reproducibly
poetry run python -m simpy_demo simulate --scenario ./scenarios/high_buffer_8hr_*
```

## Next Steps

- **[Products & Economics](products-economics.md)** - Configure SKU economics
- **[Outputs](outputs.md)** - Analyze simulation results
- **[Buffer Optimization Tutorial](../tutorials/buffer-optimization.md)** - Hands-on experiment
