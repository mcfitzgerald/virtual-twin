# Digital Twin Architecture

## Configuration Flow

```mermaid
flowchart TB
    subgraph ConfigFiles ["config/ Directory"]
        Run["runs/baseline_8hr.yaml"]
        Scenario["scenarios/baseline.yaml"]
        Topology["topologies/cosmetics_line.yaml"]
        Equipment["equipment/*.yaml"]
        Materials["materials/cosmetics.yaml"]
    end

    subgraph Loader ["ConfigLoader"]
        LoadRun["load_run()"]
        LoadScenario["load_scenario()"]
        LoadTopology["load_topology()"]
        LoadEquipment["load_equipment()"]
        Resolve["resolve_run()"]
        Build["build_machine_configs()"]
    end

    subgraph Resolved ["ResolvedConfig"]
        RC_Run["RunConfig"]
        RC_Scenario["ScenarioConfig"]
        RC_Topology["TopologyConfig"]
        RC_Equipment["EquipmentConfig[]"]
    end

    Run --> LoadRun --> RC_Run
    RC_Run -->|scenario: baseline| LoadScenario
    Scenario --> LoadScenario --> RC_Scenario
    RC_Scenario -->|topology: cosmetics_line| LoadTopology
    Topology --> LoadTopology --> RC_Topology
    RC_Scenario -->|equipment: [Filler, ...]| LoadEquipment
    Equipment --> LoadEquipment --> RC_Equipment

    Resolve --> Resolved
    Resolved --> Build --> MachineConfig["MachineConfig[]"]
    MachineConfig --> Engine["SimulationEngine"]
```

## High-Level Architecture

```mermaid
flowchart TB
    subgraph CLI ["Command Line"]
        Args["python -m simpy_demo --run baseline_8hr"]
    end

    subgraph Engine ["SimulationEngine"]
        direction TB
        Load["1. Load & Resolve Config"]
        BuildConfigs["2. Build MachineConfigs"]
        BuildLayout["3. Build SimPy Layout"]
        StartMonitor["4. Start Monitor Process"]
        RunSim["5. env.run(until=duration)"]
        Compile["6. Compile Results"]

        Load --> BuildConfigs --> BuildLayout --> StartMonitor --> RunSim --> Compile
    end

    subgraph SimPyEnv ["SimPy Environment"]
        Source["Source<br/>(Infinite Store)"]

        subgraph Line ["Production Line"]
            Filler["Equipment: Filler"]
            Buf1["Buffer"]
            Inspector["Equipment: Inspector"]
            Buf2["Buffer"]
            Packer["Equipment: Packer"]
            Buf3["Buffer"]
            Palletizer["Equipment: Palletizer"]
        end

        Sink["Sink<br/>(Infinite Store)"]
        Reject["Reject Bin"]

        Source --> Filler --> Buf1 --> Inspector --> Buf2 --> Packer --> Buf3 --> Palletizer --> Sink
        Inspector -.->|defects| Reject
    end

    Args --> Engine
    BuildLayout --> SimPyEnv
    RunSim --> SimPyEnv

    subgraph Outputs ["Data Outputs"]
        Telemetry["df_ts: Telemetry<br/>(time-series snapshots)"]
        Events["df_ev: Event Log<br/>(state transitions)"]
    end

    Compile --> Telemetry
    Compile --> Events
```

## Equipment 6-Phase Cycle

```mermaid
flowchart TD
    subgraph EquipmentCycle ["Equipment 6-Phase Cycle"]
        Start((Start)) --> P1

        P1["PHASE 1: COLLECT<br/>yield upstream.get()<br/>State: STARVED"]
        P1 -->|batch complete| P2

        P2{"PHASE 2: BREAKDOWN<br/>Poisson check<br/>(if mtbf_min set)"}
        P2 -->|fail| Down["State: DOWN<br/>yield timeout(repair_time)"]
        Down --> P3
        P2 -->|pass| P3

        P3{"PHASE 3: MICROSTOP<br/>Bernoulli check<br/>(if jam_prob > 0)"}
        P3 -->|jam| Jam["State: JAMMED<br/>yield timeout(jam_time)"]
        Jam --> P4
        P3 -->|pass| P4

        P4["PHASE 4: EXECUTE<br/>yield timeout(cycle_time)<br/>State: EXECUTE"]
        P4 --> P5

        P5["PHASE 5: TRANSFORM<br/>Create Product<br/>(type based on output_type)"]
        P5 --> P6

        P6{"PHASE 6: INSPECT<br/>(if detection_prob > 0)"}
        P6 -->|defect detected| RejectRoute["Route to Reject"]
        P6 -->|good/undetected| Normal["Route Downstream"]

        RejectRoute --> Block["yield store.put()<br/>State: BLOCKED"]
        Normal --> Block
        Block --> P1
    end
```

## OEE Loss Mapping

```mermaid
flowchart LR
    subgraph OEE ["OEE Loss Mapping"]
        direction TB

        subgraph Availability ["Availability Loss"]
            MTBF["reliability.mtbf_min"]
            MTTR["reliability.mttr_min"]
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
            Defect --> SCRAP["Routed to Reject"]
            Detect --> SCRAP
        end
    end
```

## Configuration Files

| Directory | Purpose | Example |
|-----------|---------|---------|
| `config/runs/` | Run parameters (duration, seed, start_time) | `baseline_8hr.yaml` |
| `config/scenarios/` | What-if experiments (topology + equipment refs) | `baseline.yaml` |
| `config/topologies/` | Line structure (station order, batch sizes) | `cosmetics_line.yaml` |
| `config/equipment/` | Equipment parameters (uph, reliability, etc.) | `filler.yaml` |
| `config/materials/` | Material type definitions | `cosmetics.yaml` |

## Timestamp Handling

Timestamps are embedded during simulation (not post-hoc):

```
datetime = start_time + timedelta(seconds=env.now)
```

- `start_time` is configured in RunConfig (ISO 8601 format)
- If not specified, defaults to `datetime.now()`
- Both telemetry and events include `datetime` column

## Resolution Flow

1. **Run** → specifies scenario name
2. **Scenario** → specifies topology + equipment list + overrides
3. **Topology** → defines station order and batch sizes
4. **Equipment** → provides default parameters per station
5. **Overrides** → scenario-specific parameter changes

## CLI Usage

```bash
# Run default config
python -m simpy_demo

# Run specific config
python -m simpy_demo --run baseline_8hr

# Export to CSV
python -m simpy_demo --run baseline_8hr --export

# Use custom config directory
python -m simpy_demo --config ./my_configs --run custom_scenario
```
