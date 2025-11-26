"""Telemetry generator for creating material-type specific telemetry from config.

This module generates telemetry values based on material type configurations
defined in config/materials/*.yaml. Each telemetry field has a generator type:
- gaussian: Random normal distribution with mean/stddev
- fixed: Constant value
- expression: Computed from inputs using ExpressionEngine
- count_inputs: Count of input items
"""

import random
from abc import ABC, abstractmethod
from typing import Any, Dict, List, TYPE_CHECKING

from simpy_demo.expressions.engine import ExpressionEngine, substitute_constants_in_value

if TYPE_CHECKING:
    from simpy_demo.models import Product


class BaseGenerator(ABC):
    """Base class for telemetry field generators."""

    @abstractmethod
    def generate(
        self,
        config: Dict[str, Any],
        inputs: List["Product"],
        constants: Dict[str, Any],
    ) -> Any:
        """Generate a telemetry value.

        Args:
            config: Generator configuration from materials.yaml
            inputs: List of input products (for expression/count generators)
            constants: Dict of constants for substitution

        Returns:
            Generated telemetry value
        """
        pass


class GaussianGenerator(BaseGenerator):
    """Generate values from normal distribution."""

    def generate(
        self,
        config: Dict[str, Any],
        inputs: List["Product"],
        constants: Dict[str, Any],
    ) -> float:
        mean = config.get("mean", 0.0)
        stddev = config.get("stddev", 1.0)

        # Substitute constants if values are strings
        if isinstance(mean, str):
            mean = float(substitute_constants_in_value(mean, constants))
        if isinstance(stddev, str):
            stddev = float(substitute_constants_in_value(stddev, constants))

        return random.gauss(mean, stddev)


class FixedGenerator(BaseGenerator):
    """Generate fixed constant values."""

    def generate(
        self,
        config: Dict[str, Any],
        inputs: List["Product"],
        constants: Dict[str, Any],
    ) -> Any:
        value = config.get("value")
        if isinstance(value, str) and "${" in value:
            substituted = substitute_constants_in_value(value, constants)
            # Try to convert numeric strings to numbers
            if isinstance(substituted, str):
                try:
                    if "." in substituted:
                        return float(substituted)
                    return int(substituted)
                except ValueError:
                    return substituted
            return substituted
        return value


class ExpressionGenerator(BaseGenerator):
    """Generate values using expression evaluation."""

    def generate(
        self,
        config: Dict[str, Any],
        inputs: List["Product"],
        constants: Dict[str, Any],
    ) -> Any:
        expr = config.get("expr", "0")
        engine = ExpressionEngine(constants)
        context = {"inputs": inputs}
        return engine.evaluate(expr, context)


class CountInputsGenerator(BaseGenerator):
    """Count the number of input items."""

    def generate(
        self,
        config: Dict[str, Any],
        inputs: List["Product"],
        constants: Dict[str, Any],
    ) -> int:
        return len(inputs)


# Generator registry
GENERATORS: Dict[str, type[BaseGenerator]] = {
    "gaussian": GaussianGenerator,
    "fixed": FixedGenerator,
    "expression": ExpressionGenerator,
    "count_inputs": CountInputsGenerator,
}


class TelemetryGenerator:
    """Generate telemetry dictionaries based on material type configuration.

    Loads generator specifications from materials config and produces
    telemetry values for each material type.

    Example:
        >>> materials_config = {
        ...     "TUBE": {
        ...         "telemetry": {
        ...             "fill_level": {"generator": "gaussian", "mean": 100, "stddev": 1.0}
        ...         }
        ...     }
        ... }
        >>> gen = TelemetryGenerator(materials_config, constants)
        >>> gen.generate("TUBE", [])
        {'fill_level': 99.87}
    """

    def __init__(
        self,
        materials_types: Dict[str, Dict[str, Any]],
        constants: Dict[str, Any],
    ):
        """Initialize telemetry generator.

        Args:
            materials_types: Dict of material type name -> type config from materials.yaml
            constants: Dict of constants for ${CONST} substitution
        """
        self.materials_types = materials_types
        self.constants = constants

    def generate(
        self,
        material_type: str,
        inputs: List["Product"],
    ) -> Dict[str, Any]:
        """Generate telemetry dictionary for a material type.

        Args:
            material_type: Material type name (e.g., "TUBE", "CASE", "PALLET")
            inputs: List of input products for expression/count generators

        Returns:
            Dict of field_name -> generated value
        """
        type_config = self.materials_types.get(material_type, {})
        telemetry_config = type_config.get("telemetry", {})

        if not telemetry_config:
            return {}

        result: Dict[str, Any] = {}
        for field_name, field_config in telemetry_config.items():
            if not isinstance(field_config, dict):
                # Legacy format: just field name, no config
                continue

            generator_type = field_config.get("generator", "fixed")
            generator_class = GENERATORS.get(generator_type)

            if generator_class is None:
                raise ValueError(f"Unknown telemetry generator type: {generator_type}")

            generator = generator_class()
            result[field_name] = generator.generate(
                field_config, inputs, self.constants
            )

        return result

    def has_config_for(self, material_type: str) -> bool:
        """Check if there's telemetry config for a material type."""
        type_config = self.materials_types.get(material_type, {})
        telemetry_config = type_config.get("telemetry", {})
        return bool(telemetry_config)
