"""Equipment behavior phases.

Each phase implements a specific part of the equipment cycle.
"""

from simpy_demo.behavior.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult
from simpy_demo.behavior.phases.breakdown import BreakdownPhase
from simpy_demo.behavior.phases.collect import CollectPhase
from simpy_demo.behavior.phases.execute import ExecutePhase
from simpy_demo.behavior.phases.inspect import InspectPhase
from simpy_demo.behavior.phases.microstop import MicrostopPhase
from simpy_demo.behavior.phases.transform import TransformPhase

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
