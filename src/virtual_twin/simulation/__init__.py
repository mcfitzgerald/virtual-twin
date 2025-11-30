"""Simulation module for running production line simulations."""

from virtual_twin.simulation.layout import (
    LayoutBuilder,
    LayoutResult,
    NodeConnections,
    RoutingRule,
    build_layout_from_graph,
)

# Note: execute_scenario is not exported here to avoid circular imports.
# Import directly from virtual_twin.simulation.runtime when needed.

__all__ = [
    "LayoutBuilder",
    "LayoutResult",
    "NodeConnections",
    "RoutingRule",
    "build_layout_from_graph",
]
