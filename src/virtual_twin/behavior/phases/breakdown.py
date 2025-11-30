"""Breakdown phase: Check for and handle machine breakdowns (availability loss)."""

import math
import random
from typing import TYPE_CHECKING, Any, Generator, List

from virtual_twin.behavior.phases.base import Phase, PhaseContext, PhaseResult

if TYPE_CHECKING:
    from virtual_twin.models import MachineConfig, Product


class BreakdownPhase(Phase):
    """Check for breakdown and handle repair time.

    Uses Poisson probability based on cycle time and MTBF.
    P(fail) = 1 - e^(-cycle_time/mtbf)

    When breakdown occurs:
    1. Machine enters DOWN state
    2. Waits for exponentially distributed repair time based on MTTR
    3. Returns to normal operation
    """

    name = "breakdown"

    def execute(
        self,
        env: Any,
        config: "MachineConfig",
        inputs: List["Product"],
        context: PhaseContext,
    ) -> Generator[Any, None, PhaseResult]:
        """Check for breakdown and wait for repair if needed."""
        # Note: is_enabled() ensures mtbf_min is not None before this runs
        mtbf_min = config.reliability.mtbf_min
        assert mtbf_min is not None  # Guarded by is_enabled()
        mtbf_sec = mtbf_min * 60  # minutes to seconds
        p_fail = 1.0 - math.exp(-config.cycle_time_sec / mtbf_sec)

        if random.random() < p_fail:
            # Machine failed - log state and wait for repair
            if context.log_state:
                context.log_state("DOWN")

            repair_time = random.expovariate(
                1.0 / (config.reliability.mttr_min * 60)
            )
            yield env.timeout(repair_time)

            return PhaseResult(
                state_change="DOWN",
                duration_sec=repair_time,
            )

        return PhaseResult()

    def is_enabled(self, config: "MachineConfig") -> bool:
        """Breakdown phase only runs if MTBF is configured."""
        return config.reliability.mtbf_min is not None
