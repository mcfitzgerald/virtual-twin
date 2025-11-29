# Installation

## Prerequisites

- **Python 3.10+** - The simulation uses modern Python features
- **Poetry** - Dependency management and virtual environments

### Installing Poetry

=== "macOS/Linux"

    ```bash
    curl -sSL https://install.python-poetry.org | python3 -
    ```

=== "Windows"

    ```powershell
    (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
    ```

Verify installation:
```bash
poetry --version
# Poetry (version 1.8.0)
```

## Install SimPy-Demo

### 1. Clone the Repository

```bash
git clone https://github.com/michael/simpy-demo.git
cd simpy-demo
```

### 2. Install Dependencies

```bash
poetry install
```

This installs:

- **simpy** - Discrete event simulation framework
- **pydantic** - Data validation and settings management
- **pandas** - Data analysis and export
- **pyyaml** - YAML configuration parsing
- **jinja2** - Template engine for scenario generation

### 3. Verify Installation

```bash
poetry run python -m simpy_demo --help
```

Expected output:
```
usage: python -m simpy_demo [-h] [--run NAME] [--config PATH] [--export] [--output PATH]
                           {run,configure,simulate} ...

SimPy Production Line Simulator

positional arguments:
  {run,configure,simulate}
    run                 Run simulation directly
    configure           Generate scenario bundle
    simulate            Run scenario from bundle

options:
  -h, --help            show this help message and exit
  --run NAME            Run config name (default: baseline_8hr)
  --config PATH         Config directory (default: config)
  --export              Export results to CSV
  --output PATH         Output directory (default: output)
```

## Project Structure

After installation, your directory looks like:

```
simpy-demo/
├── config/                 # YAML configuration files
│   ├── runs/              # Simulation run configs
│   ├── scenarios/         # What-if experiment configs
│   ├── topologies/        # Line structure configs
│   ├── equipment/         # Equipment parameter configs
│   ├── products/          # SKU definitions
│   └── behaviors/         # Phase behavior configs
├── src/simpy_demo/        # Python source code
├── docs/                  # Documentation (you're here!)
├── output/                # Simulation results (created on export)
└── pyproject.toml         # Project dependencies
```

## Next Steps

- **[Quickstart](quickstart.md)** - Run your first simulation
- **[Concepts](concepts.md)** - Learn about DES and OEE
