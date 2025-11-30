# Glossary

Terminology used in Virtual Twin and manufacturing simulation.

## Manufacturing Terms

### Availability
The percentage of scheduled time that equipment is available to run. Reduced by breakdowns and changeovers.

$$
\text{Availability} = \frac{\text{Operating Time}}{\text{Scheduled Time}}
$$

### Batch Size
The number of input units processed together in one cycle. For example, a packer with `batch_in: 12` collects 12 tubes before producing 1 case.

### Blocking
When a machine cannot output because the downstream buffer is full. The machine enters the BLOCKED state.

### Buffer
A storage location between machines that holds work-in-process (WIP). Buffers decouple machines and absorb variation.

### Changeover
The time required to switch production from one product to another. Not currently modeled in Virtual Twin.

### Conversion Cost
The cost of transforming raw materials into finished goods, including labor, energy, and overhead.

$$
\text{Conversion Cost} = \sum(\text{Time} \times \text{Cost Rates})
$$

### CPG
Consumer Packaged Goods. Products sold to consumers through retail, such as food, beverages, toiletries, and cosmetics.

### Cycle Time
The time required to process one unit (or batch). In Virtual Twin:

$$
\text{Cycle Time (sec)} = \frac{3600}{\text{UPH}}
$$

### Defect
A product that does not meet quality specifications. Defects may be detected (scrapped) or escape to downstream.

### Defect Rate
The probability that a produced unit is defective.

### Detection Probability
The probability that an inspection process detects a defect.

### Downtime
Time when equipment is not available due to breakdowns or maintenance.

---

## OEE Terms

### OEE (Overall Equipment Effectiveness)
A metric measuring manufacturing productivity as the product of Availability, Performance, and Quality.

$$
\text{OEE} = \text{Availability} \times \text{Performance} \times \text{Quality}
$$

| OEE Level | Interpretation |
|-----------|----------------|
| < 65% | Poor |
| 65-75% | Typical |
| 75-85% | Good |
| > 85% | World-class |

### Availability Loss
Time lost due to equipment failures (breakdowns) and setup time.

### Performance Loss
Output lost due to speed reductions, micro-stops, and idling.

### Quality Loss
Output lost due to defects and rework.

### MTBF (Mean Time Between Failures)
Average time between equipment breakdowns. Higher MTBF = better reliability.

### MTTR (Mean Time To Repair)
Average time required to repair equipment after a breakdown. Lower MTTR = faster recovery.

---

## Simulation Terms

### DES (Discrete Event Simulation)
A simulation approach where state changes occur at discrete points in time (events), rather than continuously.

### Environment
In SimPy, the simulation environment manages the event queue and advances simulation time.

### Event
An instantaneous occurrence that changes system state. Examples: machine starts, machine finishes, breakdown occurs.

### Generator
A Python function using `yield` to produce values incrementally. SimPy processes are implemented as generators.

### Process
In SimPy, a generator function that models a component's behavior over time by yielding events.

### Random Seed
A number that initializes the random number generator. Same seed = same random sequence = reproducible results.

### SimPy
A Python library for discrete event simulation using generator-based coroutines.

### Store
In SimPy, a resource for storing and retrieving items. Used to model buffers between machines.

### Telemetry
Time-series data captured during simulation, including production counts, buffer levels, and machine states.

### Timeout
In SimPy, an event that completes after a specified duration. Used to model processing time.

---

## Production Line Terms

### Case
An intermediate unit of packaging containing multiple primary units (e.g., 12 tubes per case).

### Filler
A machine that fills containers (tubes, bottles) with product.

### Inspector
A machine that checks product quality and routes defective items to reject.

### Line Balancing
Designing a production line so all stations have equal cycle times, maximizing throughput.

### Material Type
The type of item flowing through the line: TUBE, CASE, PALLET, or NONE (raw material).

### Packer
A machine that groups primary units into cases.

### Pallet
A unit of shipping containing multiple cases (e.g., 60 cases per pallet).

### Palletizer
A machine that stacks cases onto pallets.

### Starvation
When a machine cannot operate because the upstream buffer is empty. The machine enters the STARVED state.

### Station
A processing location in the production line, typically containing one machine.

### Throughput
The rate of output from a process, typically measured in units per hour (UPH).

### Topology
The structure of a production line, defining how stations are connected.

### UPH (Units Per Hour)
The designed output rate of a machine.

### V-Curve
The relationship between station position and speed in a balanced line, where all stations have equal UPH.

### WIP (Work In Process)
Partially completed products currently in the production system. Stored in buffers between machines.

---

## Configuration Terms

### Config Resolution
The process of loading and merging configuration files: Run → Scenario → Topology → Equipment.

### Override
A parameter modification applied to base equipment configuration in a scenario.

### ResolvedConfig
A fully resolved configuration with all references loaded and overrides applied.

### Run Config
Configuration specifying simulation parameters: duration, seed, scenario reference.

### Scenario Config
Configuration specifying a what-if experiment: topology, equipment, overrides.

---

## Economic Terms

### Gross Margin
Revenue minus costs (material + conversion).

$$
\text{Gross Margin} = \text{Revenue} - \text{Material Cost} - \text{Conversion Cost}
$$

### Material Cost
The cost of raw materials consumed, based on total output (including defects).

### Revenue
Income from selling good (non-defective) products.

### Selling Price
The price per unit of finished goods sold.

---

## Machine States

| State | Description |
|-------|-------------|
| STARVED | Waiting for input (upstream buffer empty) |
| EXECUTE | Actively processing (value-add time) |
| DOWN | Broken down, undergoing repair |
| JAMMED | Experiencing a micro-stop/jam |
| BLOCKED | Waiting to output (downstream buffer full) |
