"""Equipment behavior system with configurable phases.

This module provides a pluggable behavior system for equipment.
Behaviors are defined in YAML and executed by the orchestrator.
"""

from simpy_demo.behavior.orchestrator import (
    BehaviorConfig,
    BehaviorOrchestrator,
    DEFAULT_BEHAVIOR,
    create_default_behavior,
)
from simpy_demo.behavior.phases import (
    PHASE_REGISTRY,
    BreakdownPhase,
    CollectPhase,
    ExecutePhase,
    InspectPhase,
    MicrostopPhase,
    Phase,
    PhaseConfig,
    PhaseContext,
    PhaseResult,
    TransformPhase,
    get_phase_class,
)

__all__ = [
    # Orchestrator
    "BehaviorOrchestrator",
    "BehaviorConfig",
    "DEFAULT_BEHAVIOR",
    "create_default_behavior",
    # Phase base
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
    # Registry
    "PHASE_REGISTRY",
    "get_phase_class",
]
