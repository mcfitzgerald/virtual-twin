The following document serves as the technical transfer manual for the SimPy Production Line Digital Twin. It documents the architectural decisions, design patterns, and domain logic used to build the simulation engine.

-----

# Technical Transfer: CPG Production Line Digital Twin

**Version:** 1.0
**Frameworks:** SimPy, Pydantic, Pandas
**Scope:** Discrete Event Simulation (DES) & Synthetic Data Generation

-----

## 1\. Executive Summary

[cite\_start]This software serves a dual purpose: it is an **Operational Simulator** for validating production line throughput and accumulation strategies[cite: 159, 233], and a **Synthetic Data Generator** creating labeled datasets for Machine Learning (Predictive Maintenance and Process Mining).

The system models a high-speed Consumer Packaged Goods (CPG) line, accounting for physics (V-Curve rates), stochastic reliability (breakdowns/jams), and quality control (scrap rates).

-----

## 2\. Architecture & Design Patterns

The system avoids "spaghetti code" by adhering to strict Separation of Concerns using the following architectural patterns:

### A. The Core Simulation Pattern (Generator-Based Co-routines)

Unlike thread-based parallelism, this system uses **SimPy’s Cooperative Multitasking**.

  * **The Engine:** The `simpy.Environment` acts as a priority queue scheduler. It moves time forward only when events occur, allowing simulation of 8-hour shifts in milliseconds.
  * **The Agents:** Every machine (`SmartEquipment`) is a Python Generator (`yield`).
  * **The Handshake:** Processes do not communicate directly. They synchronize via **Resources** (Buffers/Stores). The pattern `yield store.get()` suspends the machine process until material is available, naturally modeling "Starvation."

### B. Configuration as Code (Schema Validation)

We use **Pydantic** to decouple the *Simulation Logic* from the *Experiment Design*.

  * **Pattern:** Data Transfer Objects (DTOs).
  * **Implementation:** `MachineConfig` and `ScenarioConfig` classes enforce types and constraints (e.g., MTBF must be a float). This prevents runtime errors deep in the simulation loop.

### C. The Composite Material Pattern (Traceability)

To model traceability and quality, materials are not simple counters. We use the **Composite Pattern**:

  * **Leaf Node:** `Tube` (Fundamental unit).
  * **Composite Nodes:** `Case` (Contains list of Tubes) and `Pallet` (Contains list of Cases).
  * **Benefit:** This allows recursive attribute calculation (e.g., `Pallet.is_defective` is true if *any* tube inside it is defective).

-----

## 3\. Link to Reality: Physics & OEE Mapping

The simulation logic is grounded in industry-standard definitions of Overall Equipment Effectiveness (OEE) and line dynamics.

### A. The V-Curve (Line Balancing)

[cite\_start]The code implements the **V-Curve** principle[cite: 165], where upstream machines "push" and downstream machines "pull" to protect the critical bottleneck.

  * **Code Implementation:**
      * [cite\_start]`Depalletizer` (11k UPH) \> `Filler` (10k UPH - **Neck**)[cite: 166].
      * `Palletizer` (13k UPH) \> `Filler`.
  * [cite\_start]**Reality Link:** This design deliberately creates accumulation opportunities to absorb minor stops[cite: 167].

### B. OEE Loss Categories

[cite\_start]We map code logic directly to OEE standard losses[cite: 87, 123]:

| OEE Component | Simulation Logic | Real-World Equivalent |
| :--- | :--- | :--- |
| **Availability** | `mtbf_min` (Time-based check) | Motor failure, shift change, cleaning. |
| **Performance** | `jam_prob` (Cycle-based check) | [cite\_start]Bottle tipping, sensor misread, micro-stops[cite: 130]. |
| **Quality** | `defect_rate` & `Inspector` routing | [cite\_start]Fill level variance, bad seals, rework[cite: 110]. |

### C. Accumulation & Constraints

  * **Code Implementation:** `simpy.Store(capacity=N)`.
  * **Reality Link:** This models physical conveyor space. [cite\_start]When `Buffer.put()` blocks, it simulates the "Protection of the bottleneck"[cite: 161, 348]. [cite\_start]The simulation proves that increasing `buffer_capacity` directly improves OEE by decoupling machine failures[cite: 233].

-----

## 4\. How to Run

### This project is managed with poetry

Review pyproject.toml

### Execution

Run the script directly. It is self-contained with a default "White Paper" scenario.

```poetry run digital_twin.py```

### Configuration (Scenario Testing)

Modify the `ScenarioConfig` block at the bottom of the script to test hypotheses:

1.  **Test Accumulation:** Change `buffer_capacity` on the Filler from 50 to 500.
2.  **Test Reliability:** Improve `mtbf_min` on the Packer to see impact on Total Output.
3.  **Test Speed:** Change `uph` to break the V-Curve and observe the increase in `BLOCKED` states.

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

1.  **Complex Routing (DAGs):** currently the line is linear ($A \to B \to C$). Refactor `ProductionLine` to support Directed Acyclic Graphs (splitting flow to two packers, merging streams).
2.  [cite\_start]**Shift Logic:** Add a "Shift Scheduler" process that triggers a global `Preempt` event every 8 hours to simulate worker breaks and changeovers[cite: 101].
3.  **Financial Modeling:** Decorate the `Product` class with `cost_of_goods_sold` and `Machine` class with `energy_kwh`. [cite\_start]Use the simulation to calculate the exact cost per pallet under different failure scenarios[cite: 307].
4.  **Hardware-in-the-Loop:** Replace the `random.random()` failure check with a real-time API call to an MQTT broker, allowing the simulation to "shadow" a real line in real-time.