"""Safe expression evaluator using AST parsing.

This module provides a safe expression evaluator that:
1. Substitutes ${CONSTANT_NAME} placeholders with values from constants.yaml
2. Evaluates arithmetic expressions (+, -, *, /)
3. Supports aggregate functions: sum(), len(), max(), min()

Security: Uses AST parsing instead of eval() to prevent code injection.
"""

import ast
import operator
import re
from typing import Any, Callable, Dict


def get_nested(obj: Any, path: str) -> Any:
    """Get a nested attribute from an object using dot notation.

    Args:
        obj: Object or dict to get value from
        path: Dot-separated path (e.g., 'telemetry.weight')

    Returns:
        The value at the path, or 0 if not found
    """
    parts = path.split(".")
    current = obj
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part, 0)
        elif hasattr(current, part):
            current = getattr(current, part)
        else:
            return 0
    return current


class ExpressionEngine:
    """Safe expression evaluator using AST parsing.

    Supports:
    - ${CONSTANT_NAME} substitution from constants dict
    - Arithmetic: +, -, *, /
    - Functions: sum(inputs, 'field'), len(inputs), max(inputs, 'field'), min(inputs, 'field')

    Example:
        >>> engine = ExpressionEngine({"TUBE_WEIGHT_G": 100, "CASE_TARE_G": 50})
        >>> engine.evaluate("sum(inputs, 'weight') + ${CASE_TARE_G}", {"inputs": products})
    """

    OPERATORS: Dict[type, Callable[[Any, Any], Any]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
    }

    UNARY_OPERATORS: Dict[type, Callable[[Any], Any]] = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def __init__(self, constants: Dict[str, Any]):
        """Initialize with constants dict.

        Args:
            constants: Dict of constant names to values (from constants.yaml)
        """
        self.constants = constants

    def evaluate(self, expr: str, context: Dict[str, Any]) -> Any:
        """Evaluate expression with context.

        Args:
            expr: Expression string with ${CONST} placeholders and/or functions
            context: Dict with 'inputs' list and other context variables

        Returns:
            Evaluated result (number or string)

        Raises:
            ValueError: If expression contains unknown constants or invalid syntax
        """
        # Step 1: Substitute ${CONSTANT} placeholders
        substituted = self._substitute_constants(expr)

        # Step 2: Parse AST
        try:
            tree = ast.parse(substituted, mode="eval")
        except SyntaxError as e:
            raise ValueError(f"Invalid expression syntax: {expr}") from e

        # Step 3: Evaluate safely
        return self._eval_node(tree.body, context)

    def _substitute_constants(self, expr: str) -> str:
        """Replace ${CONSTANT_NAME} with values from constants dict."""
        pattern = r"\$\{(\w+)\}"

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in self.constants:
                raise ValueError(f"Unknown constant: {key}")
            value = self.constants[key]
            # Quote strings, leave numbers as-is
            if isinstance(value, str):
                return repr(value)
            return str(value)

        return re.sub(pattern, replace, expr)

    def _eval_node(self, node: ast.expr, context: Dict[str, Any]) -> Any:
        """Recursively evaluate an AST node."""
        # Numeric literals
        if isinstance(node, ast.Constant):
            return node.value

        # For older Python compatibility (ast.Num deprecated but may appear)
        if isinstance(node, ast.Num):  # type: ignore[attr-defined]
            return node.n  # type: ignore[attr-defined]

        if isinstance(node, ast.Str):  # type: ignore[attr-defined]
            return node.s  # type: ignore[attr-defined]

        # Binary operations (+, -, *, /)
        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left, context)
            right = self._eval_node(node.right, context)
            op_func = self.OPERATORS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op_func(left, right)

        # Unary operations (+x, -x)
        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand, context)
            unary_op_func: Callable[[Any], Any] | None = self.UNARY_OPERATORS.get(
                type(node.op)
            )
            if unary_op_func is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            return unary_op_func(operand)

        # Function calls
        if isinstance(node, ast.Call):
            return self._eval_call(node, context)

        # Variable names
        if isinstance(node, ast.Name):
            name = node.id
            if name in context:
                return context[name]
            raise ValueError(f"Unknown variable: {name}")

        raise ValueError(f"Unsupported AST node type: {type(node).__name__}")

    def _eval_call(self, node: ast.Call, context: Dict[str, Any]) -> Any:
        """Evaluate a function call node."""
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function names are supported")

        func_name = node.func.id
        args = [self._eval_node(arg, context) for arg in node.args]

        # Get the inputs from context
        if func_name in ("sum", "max", "min"):
            if len(args) != 2:
                raise ValueError(f"{func_name}() requires 2 arguments: (items, 'field')")
            items, field_path = args
            if not isinstance(items, list):
                raise ValueError(f"First argument to {func_name}() must be a list")
            if not isinstance(field_path, str):
                raise ValueError(f"Second argument to {func_name}() must be a string field path")

            values = [get_nested(item, field_path) for item in items]
            if func_name == "sum":
                return sum(values)
            elif func_name == "max":
                return max(values) if values else 0
            else:  # min
                return min(values) if values else 0

        elif func_name == "len":
            if len(args) != 1:
                raise ValueError("len() requires 1 argument")
            items = args[0]
            if not isinstance(items, list):
                raise ValueError("Argument to len() must be a list")
            return len(items)

        elif func_name == "count":
            # count(inputs) is an alias for len(inputs)
            if len(args) != 1:
                raise ValueError("count() requires 1 argument")
            items = args[0]
            if not isinstance(items, list):
                raise ValueError("Argument to count() must be a list")
            return len(items)

        else:
            raise ValueError(f"Unknown function: {func_name}")


def substitute_constants_in_value(value: Any, constants: Dict[str, Any]) -> Any:
    """Substitute ${CONSTANT} in a single value (string or nested dict).

    Args:
        value: The value to process
        constants: Dict of constant names to values

    Returns:
        The value with constants substituted
    """
    if isinstance(value, str) and "${" in value:
        pattern = r"\$\{(\w+)\}"

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in constants:
                raise ValueError(f"Unknown constant: {key}")
            return str(constants[key])

        return re.sub(pattern, replace, value)
    elif isinstance(value, dict):
        return {k: substitute_constants_in_value(v, constants) for k, v in value.items()}
    elif isinstance(value, list):
        return [substitute_constants_in_value(item, constants) for item in value]
    return value
