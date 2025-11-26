# Goal

Create a simple but powerful and configurable and extensible simulation of a filling line using the python Simpy package. The desired output is MES and production data to analyze OEE, production performance, and economics (costs, scrap, margin, etc) 
The filling line has three pieces of equipment, a filler (filles tubes/bottles), a packer (loads tubes/bottles into packs), a palletizer (loads packs on pallets).
The equipment is configured on a production line. The production line has a configurable topology, e.g., filler>packer>palletizer.
The equipment has configurable parameters like speed, volume, etc; configurable stochastic failure modes (stops, mtbf, breakdowns), it has energy and conversion costs and labor params too
The lines produce products. products are also configurable with sku name, characteristcs, economics factors. Products impact line performance (not all products run the same)
Finishes goods are configurable: sizes, units in pack, packs on pallet, etc
We can simulate multiple lines, run different products on lines. We will start with one line, but want to plan for composability, e.g. we can run a campaign of different skus but stringin line simulations together.
Separate code from data. Instantiate entities (equipment, line, product, etc) based on config! 

All configs are in yaml files. This is critical. 

Use appropriate simpy patterns, use context7 for simpy docs

How i want to run the simulation:

1) configure all configurables (we can start using the defaults we already have) by editing yamls
2) run `configure` to build out classes and code into a `sicenario` from teh config files -- the simulation is a complete code file that can run independently, each file is a `scenario` and should be tagged in filename somehow to track them
3) run `simulate` to run a scenario and generate output, output should be like the current telemetry and events and stored as csvs (eventually we will want to write and store to database)

Flow: `configure` > `simulate` > output

We should be probable bundle the config and scenario files for each scenario for auditing and comparison as we will be running different scenarios.
