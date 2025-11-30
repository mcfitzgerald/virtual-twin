"""Equipment behavior phases.

Each phase implements a specific part of the equipment cycle.
"""

from virtual_twin.behavior.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult
from virtual_twin.behavior.phases.breakdown import BreakdownPhase
from virtual_twin.behavior.phases.collect import CollectPhase
from virtual_twin.behavior.phases.execute import ExecutePhase
from virtual_twin.behavior.phases.inspect import InspectPhase
from virtual_twin.behavior.phases.microstop import MicrostopPhase
from virtual_twin.behavior.phases.transform import TransformPhase

__all__ = [
    # Base classes
    "Phase",
    "PhaseConfig",
    "PhaseContext",
    "PhaseResult",
    # Phase implementations
    "CollectPhase",
    "BreakdownPhase",
    "MicrostopPhase",
    "ExecutePhase",
    "TransformPhase",
    "InspectPhase",
]

# Registry of available phase handlers
PHASE_REGISTRY: dict[str, type[Phase]] = {
    "CollectPhase": CollectPhase,
    "BreakdownPhase": BreakdownPhase,
    "MicrostopPhase": MicrostopPhase,
    "ExecutePhase": ExecutePhase,
    "TransformPhase": TransformPhase,
    "InspectPhase": InspectPhase,
}


def get_phase_class(handler_name: str) -> type[Phase]:
    """Get phase class by handler name."""
    if handler_name not in PHASE_REGISTRY:
        raise ValueError(f"Unknown phase handler: {handler_name}")
    return PHASE_REGISTRY[handler_name]
