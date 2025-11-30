# Tutorial: Buffer Optimization

Learn how to find optimal buffer sizes by running multiple scenarios and analyzing the results.

## Goal

Determine the optimal buffer capacity for the Filler station by testing multiple configurations.

## The Buffer Trade-off

| Small Buffers | Large Buffers |
|---------------|---------------|
| Less work-in-process (WIP) | More WIP |
| Shorter lead time | Longer lead time |
| More starvation/blocking | Less starvation/blocking |
| Lower throughput | Higher throughput |

The goal is to find the "sweet spot" where throughput is maximized without excessive WIP.

## Step 1: Create Test Scenarios

Create scenarios with different buffer sizes:

```bash
# Create scenarios for buffer sizes: 50, 100, 200, 400, 800
for size in 50 100 200 400 800; do
  cat > config/scenarios/buffer_test_${size}.yaml << EOF
name: buffer_test_${size}
topology: cosmetics_line
equipment:
  - Filler
  - Inspector
  - Packer
  - Palletizer
overrides:
  Filler:
    buffer_capacity: ${size}
  Inspector:
    buffer_capacity: ${size}
  Packer:
    buffer_capacity: ${size}
EOF
done
```

Create run configs:

```bash
for size in 50 100 200 400 800; do
  cat > config/runs/buffer_${size}_8hr.yaml << EOF
name: buffer_${size}_8hr
scenario: buffer_test_${size}
product: fresh_toothpaste_5oz
duration_hours: 8.0
random_seed: 42
telemetry_interval_sec: 300.0
start_time: "2025-01-06T06:00:00"
EOF
done
```

## Step 2: Run All Scenarios

```bash
for size in 50 100 200 400 800; do
  echo "Running buffer size: $size"
  poetry run python -m virtual_twin --run buffer_${size}_8hr --export
done
```

## Step 3: Analyze Results

Create an analysis script:

```python
# buffer_analysis.py
import pandas as pd
import glob

results = []

for size in [50, 100, 200, 400, 800]:
    # Find the telemetry file
    pattern = f"output/telemetry_buffer_{size}_8hr_*.csv"
    files = glob.glob(pattern)

    if not files:
        print(f"Warning: No file found for buffer size {size}")
        continue

    df = pd.read_csv(files[0])

    results.append({
        "buffer_size": size,
        "pallets": df["pallets_produced"].sum(),
        "good_pallets": df["good_pallets"].sum(),
        "revenue": df["revenue"].sum(),
        "margin": df["gross_margin"].sum(),
        "avg_filler_buffer": df["Buf_Filler"].mean(),
        "max_filler_buffer": df["Buf_Filler"].max(),
    })

df_results = pd.DataFrame(results)
print("\n=== Buffer Size Analysis ===\n")
print(df_results.to_string(index=False))

# Find optimal
optimal = df_results.loc[df_results["margin"].idxmax()]
print(f"\n=== Optimal Buffer Size ===")
print(f"Buffer size: {optimal['buffer_size']}")
print(f"Margin: ${optimal['margin']:,.2f}")
print(f"Pallets: {optimal['pallets']}")
```

Run:

```bash
python buffer_analysis.py
```

### Expected Output

```
=== Buffer Size Analysis ===

 buffer_size  pallets  good_pallets    revenue      margin  avg_filler_buffer  max_filler_buffer
          50      356           345   155250.0    85450.0               23.4                 50
         100      372           361   162450.0    92050.0               45.2                 98
         200      384           372   167400.0    97000.0               78.3                189
         400      388           376   169200.0    98600.0              142.1                312
         800      390           378   170100.0    99100.0              198.5                423

=== Optimal Buffer Size ===
Buffer size: 800
Margin: $99,100.00
Pallets: 390
```

## Step 4: Visualize Results

```python
# buffer_visualization.py
import pandas as pd
import matplotlib.pyplot as plt

# Load results from previous analysis
data = {
    "buffer_size": [50, 100, 200, 400, 800],
    "pallets": [356, 372, 384, 388, 390],
    "margin": [85450, 92050, 97000, 98600, 99100],
    "avg_buffer": [23.4, 45.2, 78.3, 142.1, 198.5]
}
df = pd.DataFrame(data)

fig, axes = plt.subplots(1, 3, figsize=(15, 4))

# Pallets vs Buffer Size
axes[0].plot(df["buffer_size"], df["pallets"], marker='o')
axes[0].set_xlabel("Buffer Size")
axes[0].set_ylabel("Pallets Produced")
axes[0].set_title("Throughput vs Buffer Size")
axes[0].grid(True)

# Margin vs Buffer Size
axes[1].plot(df["buffer_size"], df["margin"], marker='o', color='green')
axes[1].set_xlabel("Buffer Size")
axes[1].set_ylabel("Gross Margin ($)")
axes[1].set_title("Margin vs Buffer Size")
axes[1].grid(True)

# Diminishing Returns
df["marginal_gain"] = df["pallets"].diff()
axes[2].bar(df["buffer_size"][1:], df["marginal_gain"][1:])
axes[2].set_xlabel("Buffer Size")
axes[2].set_ylabel("Additional Pallets")
axes[2].set_title("Marginal Throughput Gain")
axes[2].grid(True)

plt.tight_layout()
plt.savefig("buffer_analysis.png")
print("Saved: buffer_analysis.png")
```

## Step 5: Identify Diminishing Returns

```python
# Marginal analysis
print("\n=== Marginal Analysis ===\n")
print("Buffer | Pallets | Gain | Gain%")
print("-" * 35)

prev_pallets = None
for _, row in df.iterrows():
    if prev_pallets is not None:
        gain = row["pallets"] - prev_pallets
        gain_pct = (gain / prev_pallets) * 100
        print(f"{row['buffer_size']:6} | {row['pallets']:7} | {gain:4.0f} | {gain_pct:5.1f}%")
    else:
        print(f"{row['buffer_size']:6} | {row['pallets']:7} |    - |     -")
    prev_pallets = row["pallets"]
```

### Expected Output

```
=== Marginal Analysis ===

Buffer | Pallets | Gain | Gain%
-----------------------------------
    50 |     356 |    - |     -
   100 |     372 |   16 |   4.5%
   200 |     384 |   12 |   3.2%
   400 |     388 |    4 |   1.0%
   800 |     390 |    2 |   0.5%
```

**Insight**: Diminishing returns after 200. Buffer 200→400 gives only 4 extra pallets.

## Step 6: Find the Economic Optimum

Consider WIP carrying cost:

```python
# Economic analysis with WIP cost
WIP_COST_PER_UNIT_PER_HOUR = 0.10  # $/unit/hour

data["wip_cost"] = data["avg_buffer"] * 8 * WIP_COST_PER_UNIT_PER_HOUR
data["net_margin"] = data["margin"] - data["wip_cost"]

print("\n=== Economic Optimum (including WIP cost) ===\n")
print(df[["buffer_size", "margin", "wip_cost", "net_margin"]].to_string(index=False))

optimal_idx = df["net_margin"].idxmax()
print(f"\n Economic optimum: Buffer size {df.loc[optimal_idx, 'buffer_size']}")
```

## Step 7: Statistical Validation

Run multiple seeds to validate:

```bash
# Run buffer_200 with 5 different seeds
for seed in 1 2 3 4 5; do
  cat > config/runs/buffer_200_seed${seed}.yaml << EOF
name: buffer_200_seed${seed}
scenario: buffer_test_200
product: fresh_toothpaste_5oz
duration_hours: 8.0
random_seed: ${seed}
EOF
  poetry run python -m virtual_twin --run buffer_200_seed${seed} --export
done
```

Analyze variance:

```python
import pandas as pd
import glob

results = []
for seed in range(1, 6):
    files = glob.glob(f"output/telemetry_buffer_200_seed{seed}_*.csv")
    if files:
        df = pd.read_csv(files[0])
        results.append(df["pallets_produced"].sum())

print(f"Buffer 200 Results: {results}")
print(f"Mean: {sum(results)/len(results):.1f}")
print(f"Std Dev: {pd.Series(results).std():.1f}")
```

## Clean Up

```bash
# Remove test configs
rm config/scenarios/buffer_test_*.yaml
rm config/runs/buffer_*_8hr.yaml
rm config/runs/buffer_200_seed*.yaml
```

## Summary

| Buffer Size | Pallets | Margin | Recommendation |
|-------------|---------|--------|----------------|
| 50 | 356 | $85,450 | Too small - excessive blocking |
| 100 | 372 | $92,050 | Borderline |
| **200** | **384** | **$97,000** | **Sweet spot** |
| 400 | 388 | $98,600 | Marginal improvement |
| 800 | 390 | $99,100 | Diminishing returns |

**Recommendation**: Buffer size 200 provides 98% of maximum throughput with half the WIP of size 400.

## What You Learned

1. Creating multiple scenarios with parameter variations
2. Running batch experiments
3. Analyzing results across scenarios
4. Identifying diminishing returns
5. Considering economic trade-offs (WIP cost)

## Next Steps

- **[OEE Analysis Tutorial](oee-analysis.md)** - Calculate OEE from events
- **[Scenarios Guide](../user-guide/scenarios.md)** - More scenario patterns
- **[Outputs Reference](../user-guide/outputs.md)** - Understanding output data
