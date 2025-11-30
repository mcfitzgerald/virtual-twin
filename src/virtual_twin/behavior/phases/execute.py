"""Execute phase: Process for cycle time (value-add)."""

from typing import TYPE_CHECKING, Any, Generator, List

from virtual_twin.behavior.phases.base import Phase, PhaseContext, PhaseResult

if TYPE_CHECKING:
    from virtual_twin.models import MachineConfig, Product


class ExecutePhase(Phase):
    """Execute the value-add processing time.

    This is the core production phase where the machine performs
    its operation for the configured cycle time.
    """

    name = "execute"

    def execute(
        self,
        env: Any,
        config: "MachineConfig",
        inputs: List["Product"],
        context: PhaseContext,
    ) -> Generator[Any, None, PhaseResult]:
        """Wait for cycle time to complete processing."""
        # Log execute state
        if context.log_state:
            context.log_state("EXECUTE")

        yield env.timeout(config.cycle_time_sec)

        return PhaseResult(
            state_change="EXECUTE",
            duration_sec=config.cycle_time_sec,
        )

    def is_enabled(self, config: "MachineConfig") -> bool:
        """Execute phase is always enabled."""
        return True
