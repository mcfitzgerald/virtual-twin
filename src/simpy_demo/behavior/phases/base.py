"""Base class for equipment behavior phases."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional

if TYPE_CHECKING:
    from simpy_demo.models import MachineConfig, Product


@dataclass
class PhaseConfig:
    """Configuration for a behavior phase."""

    name: str
    handler: str  # Handler class name
    enabled: str = "always"  # Condition expression or "always"
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PhaseResult:
    """Result from executing a phase."""

    outputs: List["Product"] = field(default_factory=list)
    new_defect: bool = False
    should_continue: bool = True  # False to abort cycle
    state_change: Optional[str] = None  # State to log (e.g., "DOWN", "JAMMED")
    duration_sec: float = 0.0  # Time spent in this phase


class Phase(ABC):
    """Base class for equipment behavior phases.

    Each phase implements a specific part of the equipment cycle:
    - collect: Wait for and gather inputs from upstream
    - breakdown: Check for and handle machine breakdowns
    - microstop: Check for and handle jams/microstops
    - execute: Perform the value-add processing time
    - transform: Convert inputs into outputs
    - inspect: Quality inspection and routing

    Phases are generator functions that yield SimPy events and return PhaseResult.
    """

    name: str  # Phase name for logging

    @abstractmethod
    def execute(
        self,
        env: Any,  # simpy.Environment
        config: "MachineConfig",
        inputs: List["Product"],
        context: "PhaseContext",
    ) -> Generator[Any, None, PhaseResult]:
        """Execute the phase.

        Args:
            env: SimPy environment
            config: Machine configuration
            inputs: Products collected from upstream (may be empty for collect phase)
            context: Shared context for passing data between phases

        Yields:
            SimPy events (timeout, store.get, store.put, etc.)

        Returns:
            PhaseResult with outputs, state changes, etc.
        """
        pass

    def is_enabled(self, config: "MachineConfig") -> bool:
        """Check if phase should run based on equipment config.

        Override in subclasses for conditional phases.
        Default returns True (always enabled).
        """
        return True


@dataclass
class PhaseContext:
    """Shared context passed between phases during a cycle.

    Allows phases to communicate without tight coupling.
    """

    # Upstream store for collecting inputs
    upstream: Any = None  # simpy.Store

    # Downstream stores for routing
    downstream: Any = None  # simpy.Store
    reject_store: Optional[Any] = None  # simpy.Store

    # Graph-based connections (optional)
    connections: Optional[Any] = None  # NodeConnections

    # Telemetry generator
    telemetry_gen: Optional[Any] = None  # TelemetryGenerator

    # Accumulated results during cycle
    collected_inputs: List["Product"] = field(default_factory=list)
    transformed_output: Optional["Product"] = None
    new_defect_created: bool = False
    routed_to_reject: bool = False

    # Phase-specific data (for extensibility)
    data: Dict[str, Any] = field(default_factory=dict)

    # Logging callback
    log_state: Optional[Any] = None  # Callable[[str], None]
