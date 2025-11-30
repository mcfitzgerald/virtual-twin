# Contributing

Guidelines for contributing to Virtual Twin.

## Development Setup

### Prerequisites

- Python 3.10+
- Poetry

### Clone and Install

```bash
git clone https://github.com/mcfitzgerald/virtual-twin.git
cd virtual-twin
poetry install
```

### Verify Installation

```bash
poetry run python -m virtual_twin --help
```

## Code Style

### Formatting and Linting

We use `ruff` for formatting and linting:

```bash
# Check formatting
poetry run ruff format --check src/

# Format code
poetry run ruff format src/

# Lint code
poetry run ruff check src/

# Fix auto-fixable issues
poetry run ruff check --fix src/
```

### Type Checking

We use `mypy` for type checking:

```bash
poetry run mypy src/virtual_twin/
```

### Pre-Commit

Before committing, run:

```bash
poetry run ruff format src/
poetry run ruff check src/
poetry run mypy src/virtual_twin/
```

## Project Structure

```
virtual-twin/
├── src/virtual_twin/        # Source code
│   ├── models.py          # Pydantic models
│   ├── loader.py          # Config loading
│   ├── equipment.py       # Equipment class
│   ├── engine.py          # Simulation engine
│   ├── run.py             # CLI
│   ├── behavior/          # Phase system
│   ├── topology/          # Graph topology
│   ├── simulation/        # Layout builder
│   ├── codegen/           # Scenario generation
│   └── cli/               # CLI subcommands
├── config/                # YAML configurations
├── docs/                  # Documentation
└── tests/                 # Integration tests
```

## Testing

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with verbose output
poetry run pytest -v

# Run specific test file
poetry run pytest tests/test_reality_checks.py

# Run with coverage
poetry run pytest --cov=virtual_twin
```

### Test Categories

| File | Purpose |
|------|---------|
| `test_integration.py` | Smoke tests for config loading and simulation |
| `test_outputs.py` | Schema validation for DataFrame columns |
| `test_reality_checks.py` | Manufacturing reality validation (OEE, throughput) |
| `test_cli.py` | CLI workflow tests (configure/simulate) |
| `test_optimization.py` | Optimization experiment validation |

### Adding Tests

1. Add test file in `tests/` directory
2. Use fixtures from `conftest.py`
3. Follow existing naming conventions (`test_*.py`, `test_*` functions)
4. Include docstrings explaining what's being tested

## Adding Features

### New Equipment Parameters

1. Add field to `MachineConfig` in `models.py`
2. Add default in `config/defaults.yaml`
3. Update relevant phase in `behavior/phases/`
4. Update `config-schema.md` documentation

### New Phase

1. Create phase class in `behavior/phases/`
2. Register in `PHASE_REGISTRY`
3. Add to `DEFAULT_BEHAVIOR` or custom behavior config
4. Document in architecture and API docs

### New Config Type

1. Create dataclass in `loader.py`
2. Add `load_*` method to `ConfigLoader`
3. Add to `ResolvedConfig` if needed
4. Create config directory and example
5. Document schema

## Documentation

### Building Docs

```bash
# Serve locally with hot reload
poetry run mkdocs serve

# Build static site
poetry run mkdocs build
```

### Adding Documentation

1. Create `.md` file in appropriate `docs/` subdirectory
2. Add to `nav` in `mkdocs.yml`
3. Use consistent formatting and terminology
4. Include examples

## Git Workflow

### Commit Messages

Use conventional commits:

```
feat: Add new feature
fix: Fix bug
docs: Update documentation
refactor: Code refactoring
test: Add tests
chore: Maintenance tasks
```

### Changelog

Update `CHANGELOG.md` for all changes:

1. Add entry under `[Unreleased]` or new version
2. Use semantic versioning
3. Update version in `pyproject.toml`

### Pull Requests

1. Create feature branch from `main`
2. Make changes with clear commits
3. Update documentation and changelog
4. Run linting and type checking
5. Submit PR with description

## Versioning

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

## Questions?

- Check [existing documentation](index.md)
- Review [architecture](architecture.md)
- Open an issue on GitHub
