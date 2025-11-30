# CLI Reference

Complete command-line interface reference for Virtual Twin.

## Basic Usage

```bash
poetry run python -m virtual_twin [OPTIONS] [COMMAND]
```

## Global Options

| Option | Description | Default |
|--------|-------------|---------|
| `--run NAME` | Run config name | `baseline_8hr` |
| `--config PATH` | Config directory path | `config` |
| `--export` | Export results to CSV | False |
| `--output PATH` | Output directory | `output` |
| `-h, --help` | Show help message | - |

## Commands

### Direct Run (No Subcommand)

Run a simulation directly using global options.

```bash
poetry run python -m virtual_twin --run baseline_8hr --export
```

**Examples:**

```bash
# Run default config
poetry run python -m virtual_twin

# Run specific config
poetry run python -m virtual_twin --run baseline_graph_8hr

# Export to specific directory
poetry run python -m virtual_twin --run baseline_8hr --export --output ./results

# Use custom config directory
poetry run python -m virtual_twin --config ./my_configs --run custom_run --export
```

---

### run

Explicit subcommand for running simulations.

```bash
poetry run python -m virtual_twin run [OPTIONS]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--run NAME` | Run config name | `baseline_8hr` |
| `--config PATH` | Config directory | `config` |
| `--export` | Export results to CSV | False |
| `--output PATH` | Output directory | `output` |
| `--no-db` | Skip saving to DuckDB database | False |
| `--db-path PATH` | Custom path for DuckDB file | `./virtual_twin_results.duckdb` |

**Examples:**

```bash
# Run with subcommand
poetry run python -m virtual_twin run --run baseline_8hr --export

# Same as direct run
poetry run python -m virtual_twin --run baseline_8hr --export

# Skip database storage
poetry run python -m virtual_twin run --run baseline_8hr --no-db

# Use custom database path
poetry run python -m virtual_twin run --run baseline_8hr --db-path ./my_results.duckdb
```

---

### configure

Generate a scenario bundle for reproducible runs.

```bash
poetry run python -m virtual_twin configure [OPTIONS]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--run NAME` | Run config name | Required |
| `--config PATH` | Config directory | `config` |
| `--output PATH` | Output directory for bundle | `scenarios` |
| `--dry-run` | Preview without creating files | False |

**Output:**

Creates a timestamped scenario bundle:

```
scenarios/baseline_8hr_20250129_143022/
├── scenario.py           # Executable runner
├── config_snapshot.yaml  # Frozen configuration
├── metadata.json         # Generation metadata
└── output/               # Empty (populated by simulate)
```

**Examples:**

```bash
# Generate scenario bundle
poetry run python -m virtual_twin configure --run baseline_8hr

# Preview what would be generated
poetry run python -m virtual_twin configure --run baseline_8hr --dry-run

# Output to custom directory
poetry run python -m virtual_twin configure --run baseline_8hr --output ./my_scenarios
```

---

### simulate

Run a simulation from a scenario bundle.

```bash
poetry run python -m virtual_twin simulate [OPTIONS]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--scenario PATH` | Path to scenario bundle | Required |

**Output:**

Populates the bundle's `output/` directory:

```
scenarios/baseline_8hr_20250129_143022/output/
├── telemetry.csv
├── events.csv
└── summary.json
```

**Examples:**

```bash
# Run scenario bundle
poetry run python -m virtual_twin simulate --scenario ./scenarios/baseline_8hr_20250129_143022

# Using glob pattern
poetry run python -m virtual_twin simulate --scenario ./scenarios/baseline_8hr_*
```

---

## Workflows

### Quick Run

For quick testing without scenario bundles:

```bash
poetry run python -m virtual_twin --run baseline_8hr --export
```

### Reproducible Run

For auditable, reproducible simulations:

```bash
# Step 1: Generate bundle
poetry run python -m virtual_twin configure --run baseline_8hr

# Step 2: Run from bundle
poetry run python -m virtual_twin simulate --scenario ./scenarios/baseline_8hr_*
```

### Batch Runs

Run multiple configurations:

```bash
for run in baseline_8hr high_buffer_8hr high_speed_8hr; do
  poetry run python -m virtual_twin --run $run --export
done
```

### Compare Scenarios

```bash
# Generate bundles
poetry run python -m virtual_twin configure --run baseline_8hr
poetry run python -m virtual_twin configure --run high_buffer_8hr

# Run both
poetry run python -m virtual_twin simulate --scenario ./scenarios/baseline_8hr_*
poetry run python -m virtual_twin simulate --scenario ./scenarios/high_buffer_8hr_*

# Compare configs
diff scenarios/baseline_8hr_*/config_snapshot.yaml scenarios/high_buffer_8hr_*/config_snapshot.yaml
```

---

## Output Files

### Direct Run (--export)

| File | Description |
|------|-------------|
| `output/telemetry_{run}_{timestamp}.csv` | Time-series data |
| `output/events_{run}_{timestamp}.csv` | State transition log |

### Scenario Bundle (simulate)

| File | Description |
|------|-------------|
| `{bundle}/output/telemetry.csv` | Time-series data |
| `{bundle}/output/events.csv` | State transition log |
| `{bundle}/output/summary.json` | Production, economics, OEE |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Configuration error |
| 2 | Simulation error |

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VIRTUAL_TWIN_CONFIG` | Default config directory | `config` |
| `VIRTUAL_TWIN_OUTPUT` | Default output directory | `output` |

---

## Help

```bash
# General help
poetry run python -m virtual_twin --help

# Subcommand help
poetry run python -m virtual_twin run --help
poetry run python -m virtual_twin configure --help
poetry run python -m virtual_twin simulate --help
```
