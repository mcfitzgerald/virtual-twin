# Tutorial: Custom Equipment

Learn how to create custom equipment configurations for new machines or modified parameters.

## Goal

Create a high-speed filler variant and test its impact on production.

## Step 1: Examine Existing Equipment

Look at the baseline filler configuration:

```bash
cat config/equipment/filler.yaml
```

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

## Step 2: Create High-Speed Variant

Create a new equipment config with 25% higher speed but slightly worse reliability:

```bash
cat > config/equipment/filler_highspeed.yaml << 'EOF'
name: FillerHighSpeed
uph: 5000                    # 25% faster

buffer_capacity: 250         # Larger buffer for higher throughput

reliability:
  mtbf_min: 2700             # 25% less reliable (faster = more wear)
  mtbf_max: 5400
  mttr_min: 150              # Slightly longer repairs
  mttr_max: 360

performance:
  jam_prob: 0.003            # 50% more jams at higher speed
  jam_time_sec: 30

quality:
  defect_rate: 0.012         # Slightly higher defect rate
  detection_prob: 0.0

cost_rates:
  labor_per_hour: 25.0
  energy_per_hour: 20.0      # Higher energy at faster speed
  overhead_per_hour: 12.0    # Higher maintenance overhead
EOF
```

## Step 3: Create a Scenario

Create a scenario using the high-speed filler:

```bash
cat > config/scenarios/highspeed_filler.yaml << 'EOF'
name: highspeed_filler
topology: cosmetics_line
equipment:
  - FillerHighSpeed         # Use new equipment
  - Inspector
  - Packer
  - Palletizer
EOF
```

## Step 4: Create a Run Config

```bash
cat > config/runs/highspeed_8hr.yaml << 'EOF'
name: highspeed_8hr
scenario: highspeed_filler
product: fresh_toothpaste_5oz
duration_hours: 8.0
random_seed: 42
telemetry_interval_sec: 300.0
start_time: "2025-01-06T06:00:00"
EOF
```

## Step 5: Run Both Scenarios

```bash
# Baseline
poetry run python -m simpy_demo --run baseline_8hr --export

# High-speed
poetry run python -m simpy_demo --run highspeed_8hr --export
```

## Step 6: Compare Results

```python
# compare_fillers.py
import pandas as pd

# Load results
baseline = pd.read_csv("output/telemetry_baseline_8hr_20250106_060000.csv")
highspeed = pd.read_csv("output/telemetry_highspeed_8hr_20250106_060000.csv")

print("=== Production Comparison ===")
print(f"Baseline pallets: {baseline['pallets_produced'].sum()}")
print(f"High-speed pallets: {highspeed['pallets_produced'].sum()}")
print(f"Difference: {highspeed['pallets_produced'].sum() - baseline['pallets_produced'].sum()}")

print("\n=== Economic Comparison ===")
print(f"Baseline margin: ${baseline['gross_margin'].sum():,.2f}")
print(f"High-speed margin: ${highspeed['gross_margin'].sum():,.2f}")
print(f"Difference: ${highspeed['gross_margin'].sum() - baseline['gross_margin'].sum():,.2f}")

print("\n=== Quality Comparison ===")
baseline_defects = baseline['defective_pallets'].sum()
highspeed_defects = highspeed['defective_pallets'].sum()
print(f"Baseline defects: {baseline_defects}")
print(f"High-speed defects: {highspeed_defects}")

print("\n=== Cost Comparison ===")
baseline_conv = baseline['conversion_cost'].sum()
highspeed_conv = highspeed['conversion_cost'].sum()
print(f"Baseline conversion cost: ${baseline_conv:,.2f}")
print(f"High-speed conversion cost: ${highspeed_conv:,.2f}")
```

Run:

```bash
python compare_fillers.py
```

### Expected Results

```
=== Production Comparison ===
Baseline pallets: 384
High-speed pallets: 412
Difference: 28

=== Economic Comparison ===
Baseline margin: $97,000.00
High-speed margin: $101,200.00
Difference: $4,200.00

=== Quality Comparison ===
Baseline defects: 12
High-speed defects: 16

=== Cost Comparison ===
Baseline conversion cost: $12,800.00
High-speed conversion cost: $14,560.00
```

## Step 7: Analyze Trade-offs

The high-speed filler produces more pallets but:

- Higher conversion cost (more energy, maintenance)
- More defects (higher defect rate)
- More downtime (lower MTBF)

Calculate ROI:

```python
# Additional revenue
additional_revenue = (412 - 384) * 450  # $12,600

# Additional cost
additional_cost = (14560 - 12800)  # $1,760

# Net benefit
net_benefit = additional_revenue - additional_cost
print(f"Net benefit: ${net_benefit:,.2f}")  # $10,840
```

## Step 8: Alternative - Use Overrides

Instead of creating a new equipment file, use scenario overrides:

```yaml
# config/scenarios/highspeed_override.yaml
name: highspeed_override
topology: cosmetics_line
equipment:
  - Filler
  - Inspector
  - Packer
  - Palletizer
overrides:
  Filler:
    uph: 5000
    buffer_capacity: 250
    reliability:
      mtbf_min: 2700
      mtbf_max: 5400
    performance:
      jam_prob: 0.003
    quality:
      defect_rate: 0.012
    cost_rates:
      energy_per_hour: 20.0
      overhead_per_hour: 12.0
```

This modifies the base `Filler` config without creating a new file.

## Equipment Parameter Guide

### Speed Parameters

| Parameter | Effect | Trade-off |
|-----------|--------|-----------|
| `uph` | Units per hour | Higher = more output, more wear |
| `buffer_capacity` | Output buffer size | Higher = less blocking, more WIP |

### Reliability Parameters

| Parameter | Effect | Trade-off |
|-----------|--------|-----------|
| `mtbf_min/max` | Time between failures | Lower = more downtime |
| `mttr_min/max` | Repair duration | Higher = longer outages |

### Performance Parameters

| Parameter | Effect | Trade-off |
|-----------|--------|-----------|
| `jam_prob` | Probability of jam per cycle | Higher = more micro-stops |
| `jam_time_sec` | Jam duration | Higher = longer delays |

### Quality Parameters

| Parameter | Effect | Trade-off |
|-----------|--------|-----------|
| `defect_rate` | Probability of defect | Higher = more scrap |
| `detection_prob` | Inspection accuracy | Higher = more detected defects |

### Cost Parameters

| Parameter | Effect | Trade-off |
|-----------|--------|-----------|
| `labor_per_hour` | Labor cost | Direct impact on conversion cost |
| `energy_per_hour` | Energy cost | Often higher at higher speeds |
| `overhead_per_hour` | Overhead | Maintenance, depreciation |

## Clean Up (Optional)

Remove test configs:

```bash
rm config/equipment/filler_highspeed.yaml
rm config/scenarios/highspeed_filler.yaml
rm config/runs/highspeed_8hr.yaml
```

## What You Learned

1. Equipment config structure and parameters
2. Creating new equipment variants
3. Using scenario overrides vs. new equipment files
4. Comparing scenarios and analyzing trade-offs

## Next Steps

- **[Buffer Optimization Tutorial](buffer-optimization.md)** - Optimize buffer sizes
- **[OEE Analysis Tutorial](oee-analysis.md)** - Calculate OEE from events
- **[Config Schema Reference](../reference/config-schema.md)** - All equipment parameters
