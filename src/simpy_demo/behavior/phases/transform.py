"""Transform phase: Convert inputs into output product."""

import random
from typing import TYPE_CHECKING, Any, Generator, List

from simpy_demo.behavior.phases.base import Phase, PhaseContext, PhaseResult
from simpy_demo.models import MaterialType, Product

if TYPE_CHECKING:
    from simpy_demo.models import MachineConfig


class TransformPhase(Phase):
    """Transform inputs into output product.

    Handles:
    - Defect inheritance from inputs
    - New defect creation based on defect_rate
    - Genealogy tracking
    - Pass-through for NONE output type (inspection stations)
    """

    name = "transform"

    def execute(
        self,
        env: Any,
        config: "MachineConfig",
        inputs: List["Product"],
        context: PhaseContext,
    ) -> Generator[Any, None, PhaseResult]:
        """Transform inputs into output product."""
        # Use collected inputs from context
        actual_inputs = context.collected_inputs or inputs

        # 1. Inherit defects from inputs
        has_inherited_defect = any(i.is_defective for i in actual_inputs)

        # 2. Create new defect?
        new_defect = random.random() < config.quality.defect_rate
        is_bad = has_inherited_defect or new_defect

        # 3. Create genealogy
        genealogy = [i.uid for i in actual_inputs]

        # 4. Pass-through for NONE output type (e.g., Inspection Station)
        if config.output_type == MaterialType.NONE:
            context.transformed_output = actual_inputs[0]
            context.new_defect_created = False
            return PhaseResult(
                outputs=[actual_inputs[0]],
                new_defect=False,
            )

        # 5. Create output product (telemetry simplified - no expression engine)
        output = Product(
            type=config.output_type,
            created_at=env.now,
            parent_machine=config.name,
            is_defective=is_bad,
            genealogy=genealogy,
            telemetry={},  # Simplified: no per-item telemetry generation
        )

        # Store in context for inspect phase
        context.transformed_output = output
        context.new_defect_created = new_defect

        # No SimPy events needed - just return result
        # Use a minimal yield to make this a generator
        if False:  # pragma: no cover
            yield  # type: ignore[misc]

        return PhaseResult(
            outputs=[output],
            new_defect=new_defect,
        )

    def is_enabled(self, config: "MachineConfig") -> bool:
        """Transform phase is always enabled."""
        return True
