"""Microstop phase: Check for and handle jams (performance loss)."""

import random
from typing import TYPE_CHECKING, Any, Generator, List

from simpy_demo.behavior.phases.base import Phase, PhaseContext, PhaseResult

if TYPE_CHECKING:
    from simpy_demo.models import MachineConfig, Product


class MicrostopPhase(Phase):
    """Check for microstop/jam and wait for clearance.

    Uses Bernoulli probability per cycle.
    P(jam) = config.performance.jam_prob

    When jam occurs:
    1. Machine enters JAMMED state
    2. Waits for fixed jam clearance time
    3. Returns to normal operation
    """

    name = "microstop"

    def execute(
        self,
        env: Any,
        config: "MachineConfig",
        inputs: List["Product"],
        context: PhaseContext,
    ) -> Generator[Any, None, PhaseResult]:
        """Check for jam and wait for clearance if needed."""
        if random.random() < config.performance.jam_prob:
            # Machine jammed - log state and wait for clearance
            if context.log_state:
                context.log_state("JAMMED")

            yield env.timeout(config.performance.jam_time_sec)

            return PhaseResult(
                state_change="JAMMED",
                duration_sec=config.performance.jam_time_sec,
            )

        return PhaseResult()

    def is_enabled(self, config: "MachineConfig") -> bool:
        """Microstop phase only runs if jam probability > 0."""
        return config.performance.jam_prob > 0
