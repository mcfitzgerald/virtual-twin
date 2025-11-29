# Running Simulations

SimPy-Demo offers multiple ways to run simulations, from quick one-liners to reproducible, auditable workflows.

## Direct Run (Quick)

The simplest way to run a simulation:

```bash
poetry run python -m simpy_demo --run baseline_8hr
```

Add `--export` to save results as CSV:

```bash
poetry run python -m simpy_demo --run baseline_8hr --export
```

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--run NAME` | Run config name | `baseline_8hr` |
| `--config PATH` | Config directory | `config` |
| `--export` | Export to CSV | False |
| `--output PATH` | Output directory | `output` |

### Examples

```bash
# Run with default config
poetry run python -m simpy_demo

# Run specific config
poetry run python -m simpy_demo --run baseline_graph_8hr

# Use custom config directory
poetry run python -m simpy_demo --config ./my_configs --run custom_run

# Export to specific directory
poetry run python -m simpy_demo --run baseline_8hr --export --output ./results
```

## Subcommand: run

The explicit subcommand form:

```bash
poetry run python -m simpy_demo run --run baseline_8hr --export
```

Equivalent to the direct form, but clearer in scripts.

## Two-Stage Workflow (Reproducible)

For auditable, reproducible simulations, use the configure + simulate workflow:

### Step 1: Configure

Generate a scenario bundle:

```bash
poetry run python -m simpy_demo configure --run baseline_8hr
```

This creates a timestamped directory:

```
scenarios/baseline_8hr_20250129_143022/
├── scenario.py           # Executable runner
├── config_snapshot.yaml  # Frozen configuration
├── metadata.json         # Git commit, config hash, version
└── output/               # Empty until simulation runs
```

### Step 2: Simulate

Run the scenario bundle:

```bash
poetry run python -m simpy_demo simulate --scenario ./scenarios/baseline_8hr_20250129_143022
```

Results are saved to the bundle's `output/` directory:

```
scenarios/baseline_8hr_20250129_143022/
└── output/
    ├── telemetry.csv
    ├── events.csv
    └── summary.json
```

### Dry Run

Preview what would be generated without creating files:

```bash
poetry run python -m simpy_demo configure --run baseline_8hr --dry-run
```

## Scenario Bundle Contents

### config_snapshot.yaml

A frozen copy of all resolved configuration:

```yaml
run:
  name: baseline_8hr
  scenario: baseline
  product: fresh_toothpaste_5oz
  duration_hours: 8.0
  random_seed: 42
  telemetry_interval_sec: 300.0
  start_time: "2025-01-29T06:00:00"

scenario:
  name: baseline
  topology: cosmetics_line
  equipment:
    - Filler
    - Inspector
    - Packer
    - Palletizer

equipment:
  Filler:
    name: Filler
    uph: 4000
    buffer_capacity: 200
    reliability:
      mtbf_min: 3600
      # ... all fields frozen
```

### metadata.json

Provenance information:

```json
{
  "generated_at": "2025-01-29T14:30:22.123456",
  "config_hash": "sha256:a1b2c3d4e5f6...",
  "version": "0.9.0",
  "git_commit": "abc123def456",
  "git_dirty": false
}
```

### scenario.py

A standalone runner script:

```python
#!/usr/bin/env python
"""Scenario: baseline_8hr - Generated 2025-01-29T14:30:22"""
from simpy_demo import execute_scenario
from pathlib import Path

if __name__ == "__main__":
    scenario_dir = Path(__file__).parent
    execute_scenario(scenario_dir)
```

Run directly:

```bash
cd scenarios/baseline_8hr_20250129_143022
python scenario.py
```

## Comparing Runs

### Diff Config Snapshots

Compare two scenario bundles:

```bash
diff scenarios/run_a/config_snapshot.yaml scenarios/run_b/config_snapshot.yaml
```

### Verify Reproducibility

Re-run a scenario and compare outputs:

```bash
# Original run
poetry run python -m simpy_demo simulate --scenario ./scenarios/baseline_8hr_20250129_143022

# Copy output
cp -r scenarios/baseline_8hr_20250129_143022/output output_original

# Re-run
poetry run python -m simpy_demo simulate --scenario ./scenarios/baseline_8hr_20250129_143022

# Compare
diff output_original/telemetry.csv scenarios/baseline_8hr_20250129_143022/output/telemetry.csv
```

With the same `random_seed`, outputs should be identical.

## Programmatic Usage

Use Python directly for custom workflows:

```python
from simpy_demo import SimulationEngine, ConfigLoader

# Load and run by name
engine = SimulationEngine("config")
df_telemetry, df_events = engine.run("baseline_8hr")

# Or modify config programmatically
loader = ConfigLoader("config")
resolved = loader.resolve_run("baseline_8hr")

# Change a parameter
resolved.equipment["Filler"].buffer_capacity = 500

# Build machine configs and run
machine_configs = loader.build_machine_configs(resolved)
df_telemetry, df_events = engine.run_config(
    run=resolved.run,
    machine_configs=machine_configs,
    product=resolved.product
)
```

## Output Files

### Direct Run with --export

```
output/
├── telemetry_baseline_8hr_20250129_060000.csv
└── events_baseline_8hr_20250129_060000.csv
```

### Scenario Bundle

```
scenarios/baseline_8hr_20250129_143022/output/
├── telemetry.csv
├── events.csv
└── summary.json
```

### summary.json Contents

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

## Next Steps

- **[Scenarios](scenarios.md)** - Create what-if experiments
- **[Outputs](outputs.md)** - Understand output data
- **[CLI Reference](../reference/cli.md)** - Full command reference
