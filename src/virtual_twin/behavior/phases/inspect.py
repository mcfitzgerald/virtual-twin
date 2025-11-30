"""Inspect phase: Quality inspection and routing."""

import random
from typing import TYPE_CHECKING, Any, Generator, List

from virtual_twin.behavior.phases.base import Phase, PhaseContext, PhaseResult

if TYPE_CHECKING:
    from virtual_twin.models import MachineConfig, Product


class InspectPhase(Phase):
    """Quality inspection and routing phase.

    Handles:
    - Defect detection based on detection_prob
    - Routing to reject store or downstream
    - Graph-based conditional routing (if connections available)
    - Blocking state when downstream is full
    """

    name = "inspect"

    def execute(
        self,
        env: Any,
        config: "MachineConfig",
        inputs: List["Product"],
        context: PhaseContext,
    ) -> Generator[Any, None, PhaseResult]:
        """Inspect output and route to appropriate destination."""
        output_item = context.transformed_output
        if output_item is None:
            # No output to route (shouldn't happen in normal flow)
            return PhaseResult()

        # Determine if we should route to reject
        routed_to_reject = False

        if config.quality.detection_prob > 0 and output_item.is_defective:
            if random.random() < config.quality.detection_prob:
                routed_to_reject = True

        context.routed_to_reject = routed_to_reject

        # Log blocked state while waiting for downstream
        if context.log_state:
            context.log_state("BLOCKED")

        # Route output using graph-based routing or legacy routing
        use_graph_routing = (
            context.connections is not None
            and len(context.connections.downstream_routes) > 1
        )

        if use_graph_routing and context.connections:
            # Graph-based routing: use connections to determine destination
            destination = context.connections.get_route(output_item)
            yield destination.put(output_item)
        elif routed_to_reject and context.reject_store:
            # Legacy routing: route defectives to reject store
            yield context.reject_store.put(output_item)
        else:
            # Legacy routing: route to primary downstream
            yield context.downstream.put(output_item)

        return PhaseResult(
            state_change="BLOCKED",
        )

    def is_enabled(self, config: "MachineConfig") -> bool:
        """Inspect phase is always enabled (handles routing)."""
        return True
