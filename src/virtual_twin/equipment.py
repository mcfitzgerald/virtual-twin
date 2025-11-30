"""Equipment simulation class with configurable behavior phases."""

from typing import TYPE_CHECKING, List, Optional

import simpy

from virtual_twin.aggregation import EventAggregator
from virtual_twin.behavior import BehaviorOrchestrator, DEFAULT_BEHAVIOR
from virtual_twin.models import MachineConfig, MaterialType

if TYPE_CHECKING:
    from virtual_twin.simulation.layout import NodeConnections


class Equipment:
    """Generic machine simulator with configurable behavior phases.

    Behavior is defined in YAML and executed by BehaviorOrchestrator:
    1. COLLECT: Wait for upstream material (starvation)
    2. BREAKDOWN: Poisson probability check (if reliability.mtbf_min is set)
    3. MICROSTOP: Bernoulli per-cycle check (if performance.jam_prob > 0)
    4. EXECUTE: Process for cycle_time_sec
    5. TRANSFORM: Create output based on output_type
    6. INSPECT/ROUTE: Route defectives (if quality.detection_prob > 0)

    Supports both linear (single upstream/downstream) and graph-based
    (multiple upstream/downstream with conditional routing) topologies.
    """

    def __init__(
        self,
        env: simpy.Environment,
        config: MachineConfig,
        upstream: simpy.Store,
        downstream: simpy.Store,
        reject_store: Optional[simpy.Store],
        connections: Optional["NodeConnections"] = None,
        orchestrator: Optional[BehaviorOrchestrator] = None,  # None uses DEFAULT_BEHAVIOR
        event_aggregator: Optional[EventAggregator] = None,
        debug_events: bool = False,
    ):
        """Initialize equipment.

        Args:
            env: SimPy environment
            config: Machine configuration
            upstream: Primary upstream store
            downstream: Primary downstream store
            reject_store: Store for rejected products
            connections: Optional graph-based connections for multi-path routing
            orchestrator: Behavior orchestrator (uses DEFAULT_BEHAVIOR if None)
            event_aggregator: Optional aggregator for hybrid event storage
            debug_events: If True, populate event_log for full debugging
        """
        self.env = env
        self.cfg = config
        self.upstream = upstream
        self.downstream = downstream
        self.reject_store = reject_store

        # Graph-based connections (optional)
        self._connections = connections
        self._use_graph_routing = connections is not None and len(
            connections.downstream_routes
        ) > 1

        # Behavior orchestrator (always required)
        self._orchestrator = orchestrator or BehaviorOrchestrator(DEFAULT_BEHAVIOR)

        # Event aggregation (for hybrid storage)
        self._event_aggregator = event_aggregator
        self._debug_events = debug_events

        self.items_produced = 0
        self.state = "IDLE"
        self.state_start_time = 0.0  # Track time in current state

        # Production counters by material type
        self.tubes_produced = 0
        self.cases_produced = 0
        self.pallets_produced = 0

        # Quality counters
        self.defects_created = 0
        self.defects_detected = 0
        self.defects_escaped = 0

        # Time tracking by state (for conversion cost)
        self.time_in_state: dict[str, float] = {
            "STARVED": 0.0,
            "EXECUTE": 0.0,
            "DOWN": 0.0,
            "JAMMED": 0.0,
            "BLOCKED": 0.0,
        }

        # Centralized Logs
        self.event_log: List[dict] = []

        self.process = env.process(self.run())

    def log(self, new_state: str) -> None:
        """Records state transitions for OEE calculation and time tracking."""
        if self.state != new_state:
            # Track time spent in previous state
            time_spent = self.env.now - self.state_start_time
            prev_state = self.state

            if prev_state in self.time_in_state:
                self.time_in_state[prev_state] += time_spent

            # Notify aggregator for hybrid storage (always, when present)
            if self._event_aggregator is not None:
                self._event_aggregator.on_state_change(
                    machine_name=self.cfg.name,
                    new_state=new_state,
                    sim_time_sec=self.env.now,
                    prev_state=prev_state,
                    duration_sec=time_spent,
                )

            # Only populate event_log in debug mode
            if self._debug_events:
                self.event_log.append(
                    {
                        "timestamp": self.env.now,
                        "machine": self.cfg.name,
                        "state": prev_state,
                        "event_type": "end",
                    }
                )
                self.event_log.append(
                    {
                        "timestamp": self.env.now,
                        "machine": self.cfg.name,
                        "state": new_state,
                        "event_type": "start",
                    }
                )

            self.state = new_state
            self.state_start_time = self.env.now

    def run(self):
        """Main process loop implementing configurable behavior phases.

        Uses BehaviorOrchestrator to run YAML-defined phases.
        """
        from virtual_twin.behavior.phases import PhaseContext

        self.log("STARVED")

        while True:
            # Create phase context with all necessary dependencies
            context = PhaseContext(
                upstream=self.upstream,
                downstream=self.downstream,
                reject_store=self.reject_store,
                connections=self._connections,
                log_state=self.log,
            )

            # Run the full cycle through orchestrator
            cycle_gen = self._orchestrator.run_cycle(
                self.env, self.cfg, context
            )

            # Execute cycle, yielding SimPy events and forwarding values
            try:
                # Get first event
                event = next(cycle_gen)
                while True:
                    # Yield to SimPy and get value back
                    value = yield event
                    # Send value to orchestrator and get next event
                    event = cycle_gen.send(value)
            except StopIteration:
                pass  # Cycle completed

            # Update counters from context
            output_item = context.transformed_output
            if output_item:
                self.items_produced += 1

                # Track production by type
                if output_item.type == MaterialType.TUBE:
                    self.tubes_produced += 1
                elif output_item.type == MaterialType.CASE:
                    self.cases_produced += 1
                elif output_item.type == MaterialType.PALLET:
                    self.pallets_produced += 1

            # Track defects
            if context.new_defect_created:
                self.defects_created += 1

            # Only count detection/escape if detection was enabled for this machine
            if self.cfg.quality.detection_prob > 0 and output_item and output_item.is_defective:
                if context.routed_to_reject:
                    self.defects_detected += 1
                else:
                    self.defects_escaped += 1

            # Back to waiting for material
            self.log("STARVED")

    @property
    def total_time_sec(self) -> float:
        """Total wall-clock time spent by this machine (for conversion cost)."""
        return sum(self.time_in_state.values())

    @property
    def conversion_cost(self) -> float:
        """Calculate conversion cost based on total time and cost rates."""
        hours = self.total_time_sec / 3600.0
        return hours * self.cfg.cost_rates.total_per_hour
