# Digital Twin Architecture

## Module Structure

```
src/virtual_twin/
├── __init__.py          # Public API exports
├── __main__.py          # Entry point
├── models.py            # Pydantic schemas (Product, MachineConfig)
├── loader.py            # YAML config loading & resolution
├── config.py            # Re-exports from loader
├── equipment.py         # Equipment class (generic machine)
├── engine.py            # SimulationEngine (orchestration)
├── run.py               # CLI entry point
├── behavior/            # Pluggable phase system
│   ├── orchestrator.py  # BehaviorOrchestrator
│   └── phases/          # Phase implementations
├── topology/            # Graph-based topology
│   └── graph.py         # TopologyGraph, DAG support
├── simulation/          # Layout & runtime
│   ├── layout.py        # LayoutBuilder, routing
│   └── runtime.py       # execute_scenario()
├── codegen/             # Scenario bundle generation
│   └── generator.py     # ScenarioGenerator
└── cli/                 # CLI subcommands
    ├── configure.py     # configure command
    └── simulate.py      # simulate command
```

## Configuration Hierarchy

```mermaid
flowchart TB
    subgraph ConfigFiles ["config/ Directory"]
        Run["runs/*.yaml"]
        Scenario["scenarios/*.yaml"]
        Topology["topologies/*.yaml"]
        Equipment["equipment/*.yaml"]
        Products["products/*.yaml"]
        Behaviors["behaviors/*.yaml"]
        Sources["sources/*.yaml"]
        Defaults["defaults.yaml"]
        Constants["constants.yaml"]
    end

    subgraph Resolution ["Config Resolution"]
        Run -->|scenario ref| Scenario
        Scenario -->|topology ref| Topology
        Scenario -->|equipment refs| Equipment
        Scenario -->|behavior ref| Behaviors
        Run -->|product ref| Products
        Topology -->|source ref| Sources
    end

    subgraph Resolved ["ResolvedConfig"]
        RC["Fully resolved config<br/>ready for simulation"]
    end

    Resolution --> RC
    Defaults -.->|defaults| Resolution
    Constants -.->|substitution| Resolution
```

## High-Level Architecture

```mermaid
flowchart TB
    subgraph CLI ["Command Line Interface"]
        Direct["python -m virtual_twin --run NAME"]
        Configure["python -m virtual_twin configure --run NAME"]
        Simulate["python -m virtual_twin simulate --scenario PATH"]
    end

    subgraph Codegen ["Scenario Bundle Generation"]
        Generator["ScenarioGenerator"]
        Bundle["scenarios/<name>_<timestamp>/"]
    end

    subgraph Engine ["SimulationEngine"]
        Load["1. Load & Resolve Config"]
        BuildConfigs["2. Build MachineConfigs"]
        CreateOrch["3. Create BehaviorOrchestrator"]
        BuildLayout["4. Build SimPy Layout"]
        StartMonitor["5. Start Telemetry Monitor"]
        RunSim["6. env.run(until=duration)"]
        Compile["7. Compile Results"]

        Load --> BuildConfigs --> CreateOrch --> BuildLayout --> StartMonitor --> RunSim --> Compile
    end

    subgraph SimPyEnv ["SimPy Environment"]
        Source["Source Store"]
        Line["Equipment Processes"]
        Buffers["simpy.Store Buffers"]
        Reject["Reject Bin"]
    end

    subgraph Outputs ["Data Outputs"]
        Telemetry["df_telemetry<br/>(time-series)"]
        Events["df_events<br/>(state log)"]
        Summary["summary.json<br/>(economics, OEE)"]
    end

    Direct --> Engine
    Configure --> Generator --> Bundle
    Simulate --> Bundle --> Engine
    BuildLayout --> SimPyEnv
    Compile --> Outputs
```

## CLI Workflows

```mermaid
flowchart LR
    subgraph Workflow1 ["Direct Run (Legacy)"]
        A1["--run baseline_8hr"] --> A2["Resolve Config"] --> A3["Run Simulation"] --> A4["Export CSVs"]
    end

    subgraph Workflow2 ["Configure + Simulate"]
        B1["configure --run NAME"] --> B2["Generate Bundle"]
        B2 --> B3["scenario.py<br/>config_snapshot.yaml<br/>metadata.json"]
        B3 --> B4["simulate --scenario PATH"]
        B4 --> B5["Run from Snapshot"]
        B5 --> B6["output/<br/>telemetry.csv<br/>events.csv<br/>summary.json"]
    end
```

## Scenario Bundle Structure

```mermaid
flowchart TB
    subgraph Bundle ["scenarios/baseline_8hr_20251129_143022/"]
        Scenario["scenario.py<br/>(executable runner)"]
        Snapshot["config_snapshot.yaml<br/>(frozen resolved config)"]
        Metadata["metadata.json<br/>(git commit, hash, version)"]
        Output["output/<br/>(simulation results)"]
    end

    subgraph OutputFiles ["output/"]
        Telem["telemetry.csv"]
        Events["events.csv"]
        Summary["summary.json"]
    end

    Output --> OutputFiles
```

## Behavior Orchestrator

```mermaid
flowchart TB
    subgraph BehaviorSystem ["Behavior System"]
        Config["BehaviorConfig<br/>(YAML-defined phases)"]
        Orch["BehaviorOrchestrator"]
        Registry["PHASE_REGISTRY"]
    end

    subgraph Phases ["Pluggable Phases"]
        P1["CollectPhase"]
        P2["BreakdownPhase"]
        P3["MicrostopPhase"]
        P4["ExecutePhase"]
        P5["TransformPhase"]
        P6["InspectPhase"]
    end

    subgraph Equipment ["Equipment.run()"]
        Cycle["while True:<br/>  context = PhaseContext()<br/>  yield from orchestrator.run_cycle()"]
    end

    Config --> Orch
    Registry --> Orch
    Orch --> Phases
    Equipment --> Orch
```

## Equipment 6-Phase Cycle

```mermaid
flowchart TD
    subgraph EquipmentCycle ["Equipment 6-Phase Cycle (BehaviorOrchestrator)"]
        Start((Start)) --> P1

        P1["PHASE 1: COLLECT<br/>CollectPhase<br/>yield upstream.get() × batch_in"]
        P1 -->|inputs collected| P2

        P2{"PHASE 2: BREAKDOWN<br/>BreakdownPhase<br/>(enabled if mtbf_min set)"}
        P2 -->|Poisson fail| Down["State: DOWN<br/>yield timeout(repair_time)"]
        Down --> P3
        P2 -->|pass| P3

        P3{"PHASE 3: MICROSTOP<br/>MicrostopPhase<br/>(enabled if jam_prob > 0)"}
        P3 -->|Bernoulli jam| Jam["State: JAMMED<br/>yield timeout(jam_time)"]
        Jam --> P4
        P3 -->|pass| P4

        P4["PHASE 4: EXECUTE<br/>ExecutePhase<br/>yield timeout(cycle_time_sec)"]
        P4 --> P5

        P5["PHASE 5: TRANSFORM<br/>TransformPhase<br/>Create output Product"]
        P5 --> P6

        P6{"PHASE 6: INSPECT<br/>InspectPhase<br/>Quality detection check"}
        P6 -->|defect detected| RejectRoute["Route to reject_bin"]
        P6 -->|good/undetected| Normal["Route downstream"]

        RejectRoute --> Block["yield store.put()<br/>State: BLOCKED"]
        Normal --> Block
        Block --> P1
    end
```

## Graph Topology

```mermaid
flowchart LR
    subgraph Linear ["Linear Topology (Backward Compatible)"]
        L1["Filler"] --> L2["Inspector"] --> L3["Packer"] --> L4["Palletizer"]
    end

    subgraph Graph ["Graph Topology (DAG)"]
        Source["_source"]
        G1["Filler"]
        G2["Inspector"]
        G3["Packer"]
        G4["Palletizer"]
        Sink["_sink"]
        Reject["_reject"]

        Source --> G1
        G1 --> G2
        G2 -->|"not is_defective"| G3
        G2 -->|"is_defective"| Reject
        G3 --> G4
        G4 --> Sink
    end
```

## Layout Builder

```mermaid
flowchart TB
    subgraph Input ["Input"]
        TopoGraph["TopologyGraph<br/>(nodes, edges)"]
        MachineConfigs["MachineConfig[]"]
        Orchestrator["BehaviorOrchestrator"]
    end

    subgraph Builder ["LayoutBuilder"]
        Parse["Parse topology"]
        CreateStores["Create simpy.Stores"]
        CreateEquip["Create Equipment instances"]
        SetupRouting["Setup NodeConnections<br/>(multi-path routing)"]
    end

    subgraph Output ["LayoutResult"]
        Machines["machines: dict"]
        Buffers["buffers: dict"]
        SourceStore["source_store"]
        SinkStore["sink_store"]
        RejectBin["reject_bin"]
    end

    Input --> Builder --> Output
```

## OEE Loss Mapping

```mermaid
flowchart LR
    subgraph OEE ["OEE Loss Mapping"]
        direction TB

        subgraph Availability ["Availability Loss"]
            MTBF["reliability.mtbf_min/max"]
            MTTR["reliability.mttr_min/max"]
            MTBF --> DOWN["State: DOWN"]
            MTTR --> DOWN
        end

        subgraph Performance ["Performance Loss"]
            JamProb["performance.jam_prob"]
            JamTime["performance.jam_time_sec"]
            JamProb --> JAMMED["State: JAMMED"]
            JamTime --> JAMMED
        end

        subgraph Quality ["Quality Loss"]
            Defect["quality.defect_rate"]
            Detect["quality.detection_prob"]
            Defect --> SCRAP["Routed to reject_bin"]
            Detect --> SCRAP
        end
    end
```

## Economic Model

```mermaid
flowchart LR
    subgraph Inputs ["Inputs"]
        Product["ProductConfig<br/>material_cost<br/>selling_price"]
        CostRates["CostRates<br/>labor_per_hour<br/>energy_per_hour<br/>overhead_per_hour"]
        Production["Production<br/>good_pallets<br/>total_pallets"]
        TimeInState["Equipment<br/>time_in_state{}"]
    end

    subgraph Calculations ["Calculations"]
        MatCost["Material Cost =<br/>total_pallets × material_cost"]
        ConvCost["Conversion Cost =<br/>Σ(time × cost_rates)"]
        Revenue["Revenue =<br/>good_pallets × selling_price"]
        Margin["Gross Margin =<br/>revenue - material - conversion"]
    end

    Product --> MatCost
    Product --> Revenue
    CostRates --> ConvCost
    TimeInState --> ConvCost
    Production --> MatCost
    Production --> Revenue
    MatCost --> Margin
    ConvCost --> Margin
    Revenue --> Margin
```

## Data Outputs

### Telemetry DataFrame (`df_telemetry`)

Time-series at configurable intervals (default 5 minutes) with **incremental** values:

| Category | Columns |
|----------|---------|
| Time | `time`, `datetime` |
| SKU Context | `sku_name`, `sku_description`, `size_oz`, `units_per_case`, `cases_per_pallet` |
| Production (delta) | `tubes_produced`, `cases_produced`, `pallets_produced`, `good_pallets`, `defective_pallets` |
| Quality (delta) | `defects_created`, `defects_detected` |
| Economics (delta) | `material_cost`, `conversion_cost`, `revenue`, `gross_margin` |
| Snapshots | Buffer levels, machine states |

### Events DataFrame (`df_events`)

State transition log for OEE calculation and process mining:

| Column | Description |
|--------|-------------|
| `datetime` | ISO timestamp |
| `timestamp` | Simulation seconds |
| `machine` | Equipment name |
| `state` | STARVED, EXECUTE, DOWN, JAMMED, BLOCKED |
| `event_type` | State change identifier |
| `duration` | Time in previous state |

## Configuration Files

| Directory | Purpose | Example |
|-----------|---------|---------|
| `config/runs/` | Run parameters (duration, seed, product) | `baseline_8hr.yaml` |
| `config/scenarios/` | What-if experiments (topology + equipment + overrides) | `baseline.yaml` |
| `config/topologies/` | Line structure (linear or graph format) | `cosmetics_line.yaml` |
| `config/equipment/` | Equipment parameters (uph, reliability, quality) | `filler.yaml` |
| `config/products/` | SKU definitions with economics | `fresh_toothpaste_5oz.yaml` |
| `config/behaviors/` | Phase definitions (optional) | `default_6phase.yaml` |
| `config/sources/` | Source store configuration | `infinite_raw.yaml` |
| `config/defaults.yaml` | Global default values | - |
| `config/constants.yaml` | Named constants for substitution | - |

## CLI Usage

```bash
# Direct run (legacy, still works)
python -m virtual_twin --run baseline_8hr --export

# Two-stage workflow (reproducible)
python -m virtual_twin configure --run baseline_8hr
python -m virtual_twin simulate --scenario ./scenarios/baseline_8hr_20251129_143022

# Dry run (preview bundle without creating)
python -m virtual_twin configure --run baseline_8hr --dry-run

# Subcommand form
python -m virtual_twin run --run baseline_8hr --export
```
