"""Collect phase: Wait for and gather inputs from upstream."""

from typing import TYPE_CHECKING, Any, Generator, List, cast

from virtual_twin.behavior.phases.base import Phase, PhaseContext, PhaseResult

if TYPE_CHECKING:
    from virtual_twin.models import MachineConfig, Product


class CollectPhase(Phase):
    """Collect batch_in items from upstream store.

    This phase models starvation - if upstream is empty, the machine waits.
    """

    name = "collect"

    def execute(
        self,
        env: Any,
        config: "MachineConfig",
        inputs: List["Product"],
        context: PhaseContext,
    ) -> Generator[Any, None, PhaseResult]:
        """Collect batch_in items from upstream."""
        collected: List["Product"] = []

        for _ in range(config.batch_in):
            item = cast("Product", (yield context.upstream.get()))
            collected.append(item)

        # Store collected inputs in context for downstream phases
        context.collected_inputs = collected

        return PhaseResult(outputs=collected)

    def is_enabled(self, config: "MachineConfig") -> bool:
        """Collect phase is always enabled."""
        return True
