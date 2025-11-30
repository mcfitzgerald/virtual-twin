# TODO - Future Enhancements

This document tracks planned features and improvements for simpy-demo.

## Deferred from Refactoring

### Product impact on performance
Different skus have different performance characteristics (e.g., new pack gets jammed more, etc etc)

### Campaign Support
Multi-run campaigns for batch scenario execution.

```yaml
# config/campaigns/weekly_skus.yaml
name: weekly_skus
description: "Run all SKUs for weekly planning"

runs:
  - run: fresh_toothpaste_8hr
    product: fresh_toothpaste_5oz
  - run: mint_toothpaste_8hr
    product: mint_toothpaste_5oz

output:
  aggregate: true
  format: csv
```

```bash
python -m simpy_demo campaign --campaign weekly_skus --export
```

### Multi-Line Support
Simulate multiple production lines with shared resources.

```yaml
# config/plants/main_factory.yaml
name: main_factory

lines:
  - name: line_1
    topology: cosmetics_line
    equipment_set: line_1_equipment
  - name: line_2
    topology: cosmetics_line
    equipment_set: line_2_equipment

shared_resources:
  - name: maintenance_crew
    capacity: 2
  - name: forklift
    capacity: 3
```

---

## Feature Pipeline

### Time Coordination

- **FactoryClock class**: Shared clock abstraction for multi-line coordination
  - Multiple SimPy environments syncing to same wall clock
  - Clock drift simulation (planned vs actual time)

- **Scheduled Events**: Time-based triggers independent of line state
  - Shift changes at fixed times (e.g., 14:00)
  - Scheduled breaks, maintenance windows
  - Changeovers triggered by time or production count

- **Production Plan Integration**: External schedule drives simulation
  - Load production orders with planned start/end times
  - Compare planned vs actual completion
  - Multi-product sequencing with changeovers

- **Real-time Sync**: Optional mode where simulation tracks actual wall time
  - For digital twin "live" visualization
  - Pause/resume with time alignment

### Standards Integration

- **OMAC PackML**: Align equipment states with PackML automation standard
- **ASCM SCOR-DS**: Explore how SCOR-DS metrics fit into simulation outputs

---

## CLI Improvements

- [ ] `python -m simpy_demo diff <scenario1> <scenario2>` - Compare scenario configs
- [ ] `python -m simpy_demo lint config/` - Validate YAML configs
- [ ] `python -m simpy_demo replay --scenario <path>` - Re-run with same seed

---

## Technical Debt

- [ ] Add unit tests for new CLI commands
- [ ] Add unit tests for ScenarioGenerator
- [ ] Add integration tests for configure -> simulate workflow
- [ ] Install type stubs for pandas and pyyaml (mypy warnings)
