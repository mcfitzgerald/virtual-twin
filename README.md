The following document serves as the technical transfer manual for the SimPy Production Line Digital Twin. It documents the architectural decisions, design patterns, and domain logic used to build the simulation engine.

-----

# Technical Transfer: CPG Production Line Digital Twin

**Version:** 2.0
**Frameworks:** SimPy, Pydantic, Pandas
**Scope:** Discrete Event Simulation (DES) & Synthetic Data Generation

-----

## 1\. Executive Summary

This software serves a dual purpose: it is an **Operational Simulator** for validating production line throughput and accumulation strategies, and a **Synthetic Data Generator** creating labeled datasets for Machine Learning (Predictive Maintenance and Process Mining).

The system models a high-speed Consumer Packaged Goods (CPG) line, accounting for physics (V-Curve rates), stochastic reliability (breakdowns/jams), and quality control (scrap rates).

-----

## 2\. Architecture & Design Patterns

The system uses a clean separation of concerns:

### A. Topology vs Configuration

- **Topology** (`topology.py`): Defines line structure (stations, batch sizes, output types)
- **Baseline** (`baseline.py`): Default parameter values for each station
- **Scenarios** (`config.py`): What-if experiments as sparse overrides

### B. The Core Simulation Pattern (Generator-Based Co-routines)

Unlike thread-based parallelism, this system uses **SimPy's Cooperative Multitasking**.

  * **The Engine:** The `simpy.Environment` acts as a priority queue scheduler. It moves time forward only when events occur, allowing simulation of 8-hour shifts in milliseconds.
  * **The Agents:** Every machine (`Equipment`) is a Python Generator (`yield`).
  * **The Handshake:** Processes do not communicate directly. They synchronize via **Resources** (Buffers/Stores). The pattern `yield store.get()` suspends the machine process until material is available, naturally modeling "Starvation."

### C. Configuration as Code (Schema Validation)

We use **Pydantic** to decouple the *Simulation Logic* from the *Experiment Design*.

  * **Pattern:** Data Transfer Objects (DTOs).
  * **Implementation:** `MachineConfig` with grouped parameters (`ReliabilityParams`, `PerformanceParams`, `QualityParams`) enforce types and constraints. This prevents runtime errors deep in the simulation loop.

### D. The Composite Material Pattern (Traceability)

To model traceability and quality, materials are not simple counters. We use the **Composite Pattern**:

  * **Leaf Node:** `Tube` (Fundamental unit).
  * **Composite Nodes:** `Case` (Contains list of Tubes) and `Pallet` (Contains list of Cases).
  * **Benefit:** This allows recursive attribute calculation (e.g., `Pallet.is_defective` is true if *any* tube inside it is defective).

-----

## 3\. Link to Reality: Physics & OEE Mapping

The simulation logic is grounded in industry-standard definitions of Overall Equipment Effectiveness (OEE) and line dynamics.

### A. The V-Curve (Line Balancing)

The code implements the **V-Curve** principle, where upstream machines "push" and downstream machines "pull" to protect the critical bottleneck.

  * **Code Implementation:**
      * `Inspector` (11k UPH) > `Filler` (10k UPH - **Neck**).
      * `Palletizer` (13k UPH) > `Filler`.
  * **Reality Link:** This design deliberately creates accumulation opportunities to absorb minor stops.

### B. OEE Loss Categories

We map code logic directly to OEE standard losses:

| OEE Component | Simulation Logic | Real-World Equivalent |
| :--- | :--- | :--- |
| **Availability** | `reliability.mtbf_min` (Time-based check) | Motor failure, shift change, cleaning. |
| **Performance** | `performance.jam_prob` (Cycle-based check) | Bottle tipping, sensor misread, micro-stops. |
| **Quality** | `quality.defect_rate` & Inspector routing | Fill level variance, bad seals, rework. |

### C. Accumulation & Constraints

  * **Code Implementation:** `simpy.Store(capacity=N)`.
  * **Reality Link:** This models physical conveyor space. When `Buffer.put()` blocks, it simulates the "Protection of the bottleneck". The simulation proves that increasing `buffer_capacity` directly improves OEE by decoupling machine failures.

-----

## 4\. How to Run

### This project is managed with poetry

```bash
poetry install
```

### Execution

Run with the baseline scenario:

```bash
poetry run python -m simpy_demo
```

### Configuration (Scenario Testing)

Create custom `ScenarioConfig` instances to test hypotheses:

```python
from simpy_demo import ScenarioConfig, EquipmentParams, run_simulation
from simpy_demo.models import ReliabilityParams

# Test with larger buffer
scenario = ScenarioConfig(
    name="large_buffer_test",
    equipment={
        "Filler": EquipmentParams(buffer_capacity=500)
    }
)
run_simulation(scenario)

# Test improved reliability
scenario = ScenarioConfig(
    name="improved_reliability",
    equipment={
        "Packer": EquipmentParams(
            reliability=ReliabilityParams(mtbf_min=480)  # Double MTBF
        )
    }
)
run_simulation(scenario)
```

-----

## 5\. Data Outputs

The system generates two distinct datasets useful for separate engineering tasks:

### A. Telemetry (`df_ts`)

  * **Format:** Time-series snapshot every 1.0 second.
  * **Columns:** `time`, `Buf_Filler_level`, `Filler_state`, `Packer_state`...
  * **Use Case:** Training LSTM/Transformer models to predict **Starvation Events** based on upstream buffer depletion patterns.

### B. Event Log (`df_ev`)

  * **Format:** Transactional log of state changes.
  * **Columns:** `timestamp`, `machine`, `state` (START/END), `duration`.
  * **Use Case:** Calculating shift-level OEE, Pareto analysis of downtime reasons, and Process Mining.

-----

## 6\. Possibilities for Extension

To move this from a prototype to an Enterprise Digital Twin, consider these extensions:

1.  **Complex Routing (DAGs):** currently the line is linear ($A \to B \to C$). Refactor `SimulationEngine` to support Directed Acyclic Graphs (splitting flow to two packers, merging streams).
2.  **Shift Logic:** Add a "Shift Scheduler" process that triggers a global `Preempt` event every 8 hours to simulate worker breaks and changeovers.
3.  **Financial Modeling:** Extend with `ProductSpec` containing economics (material cost, conversion cost, selling price). Use the simulation to calculate exact cost per pallet under different failure scenarios.
4.  **Hardware-in-the-Loop:** Replace the `random.random()` failure check with a real-time API call to an MQTT broker, allowing the simulation to "shadow" a real line in real-time.
