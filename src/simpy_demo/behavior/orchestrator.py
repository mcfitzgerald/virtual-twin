"""Behavior orchestrator for coordinating equipment phases."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional

from simpy_demo.behavior.phases import (
    PHASE_REGISTRY,
    Phase,
    PhaseConfig,
    PhaseContext,
    PhaseResult,
)

if TYPE_CHECKING:
    from simpy_demo.models import MachineConfig


@dataclass
class BehaviorConfig:
    """Configuration for equipment behavior.

    Defines the sequence of phases and their parameters.
    """

    name: str
    description: str = ""
    phases: List[PhaseConfig] = field(default_factory=list)


class BehaviorOrchestrator:
    """Orchestrates phase execution for equipment.

    Loads behavior configuration and executes phases in order,
    checking enabled conditions for each phase.
    """

    def __init__(self, behavior_config: BehaviorConfig):
        """Initialize orchestrator with behavior configuration.

        Args:
            behavior_config: Configuration defining phases to execute
        """
        self.config = behavior_config
        self._phase_instances: Dict[str, Phase] = {}

        # Instantiate phase handlers
        for phase_config in behavior_config.phases:
            handler_name = phase_config.handler
            if handler_name not in PHASE_REGISTRY:
                raise ValueError(f"Unknown phase handler: {handler_name}")
            phase_class = PHASE_REGISTRY[handler_name]
            self._phase_instances[phase_config.name] = phase_class()

    def should_run_phase(
        self,
        phase_config: PhaseConfig,
        machine_config: "MachineConfig",
    ) -> bool:
        """Check if a phase should run based on its enabled condition.

        Args:
            phase_config: Phase configuration with enabled condition
            machine_config: Equipment configuration

        Returns:
            True if phase should run
        """
        condition = phase_config.enabled

        # Always enabled
        if condition == "always":
            return True

        # Check phase's own is_enabled method
        phase = self._phase_instances.get(phase_config.name)
        if phase:
            return phase.is_enabled(machine_config)

        # Default to enabled
        return True

    def run_cycle(
        self,
        env: Any,  # simpy.Environment
        machine_config: "MachineConfig",
        context: PhaseContext,
    ) -> Generator[Any, Any, PhaseResult]:
        """Run a complete equipment cycle through all enabled phases.

        Args:
            env: SimPy environment
            machine_config: Equipment configuration
            context: Phase context with stores, telemetry generator, etc.

        Yields:
            SimPy events from each phase

        Returns:
            Combined PhaseResult from all phases
        """
        combined_result = PhaseResult()
        inputs: List[Any] = []

        for phase_config in self.config.phases:
            # Check if phase should run
            if not self.should_run_phase(phase_config, machine_config):
                continue

            # Get phase instance
            phase = self._phase_instances.get(phase_config.name)
            if phase is None:
                continue

            # Execute phase (it's a generator)
            phase_gen = phase.execute(env, machine_config, inputs, context)

            # Run through phase generator, yielding events and forwarding values
            result: Optional[PhaseResult] = None
            try:
                # Get first event
                event = next(phase_gen)
                while True:
                    # Yield event to SimPy and get result back
                    value = yield event
                    # Send value to phase generator and get next event
                    event = phase_gen.send(value)
            except StopIteration as e:
                result = e.value

            # Process phase result
            if result:
                # Update combined result
                if result.outputs:
                    combined_result.outputs = result.outputs
                    inputs = result.outputs  # Pass to next phase
                if result.new_defect:
                    combined_result.new_defect = True
                if not result.should_continue:
                    combined_result.should_continue = False
                    break
                combined_result.duration_sec += result.duration_sec

        return combined_result


def create_default_behavior() -> BehaviorConfig:
    """Create the default 6-phase behavior configuration.

    This matches the original hardcoded behavior in Equipment.run().
    """
    return BehaviorConfig(
        name="default_6phase",
        description="Standard 6-phase equipment cycle",
        phases=[
            PhaseConfig(
                name="collect",
                handler="CollectPhase",
                enabled="always",
            ),
            PhaseConfig(
                name="breakdown",
                handler="BreakdownPhase",
                enabled="config.reliability.mtbf_min is not None",
            ),
            PhaseConfig(
                name="microstop",
                handler="MicrostopPhase",
                enabled="config.performance.jam_prob > 0",
            ),
            PhaseConfig(
                name="execute",
                handler="ExecutePhase",
                enabled="always",
            ),
            PhaseConfig(
                name="transform",
                handler="TransformPhase",
                enabled="always",
            ),
            PhaseConfig(
                name="inspect",
                handler="InspectPhase",
                enabled="always",
            ),
        ],
    )


# Singleton default behavior
DEFAULT_BEHAVIOR = create_default_behavior()
