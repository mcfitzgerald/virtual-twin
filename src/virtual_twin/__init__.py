"""SimPy-based production line digital twin."""

from virtual_twin.behavior import (
    BehaviorConfig,
    BehaviorOrchestrator,
    BreakdownPhase,
    CollectPhase,
    DEFAULT_BEHAVIOR,
    ExecutePhase,
    InspectPhase,
    MicrostopPhase,
    Phase,
    PhaseConfig,
    PhaseContext,
    PhaseResult,
    TransformPhase,
)
from virtual_twin.cli import configure, simulate
from virtual_twin.codegen import ScenarioGenerator
from virtual_twin.config import (
    ConfigLoader,
    ConstantsConfig,
    DefaultsConfig,
    EdgeConfig,
    EquipmentConfig,
    NodeConfig,
    ResolvedConfig,
    RunConfig,
    ScenarioConfig,
    SourceConfig,
    StationConfig,
    TopologyConfig,
)
from virtual_twin.engine import SimulationEngine
from virtual_twin.equipment import Equipment
from virtual_twin.models import (
    CostRates,
    MachineConfig,
    MaterialType,
    PerformanceParams,
    Product,
    ProductConfig,
    QualityParams,
    ReliabilityParams,
)
from virtual_twin.run import run_simulation
from virtual_twin.simulation.runtime import execute_scenario
from virtual_twin.storage import connect as db_connect
from virtual_twin.storage import get_db_path, save_results
from virtual_twin.topology import (
    BufferEdge,
    CycleDetectedError,
    StationNode,
    TopologyGraph,
)

__all__ = [
    # Models
    "MaterialType",
    "Product",
    "ProductConfig",
    "MachineConfig",
    "ReliabilityParams",
    "PerformanceParams",
    "QualityParams",
    "CostRates",
    # Config
    "ConfigLoader",
    "DefaultsConfig",
    "ConstantsConfig",
    "SourceConfig",
    "RunConfig",
    "ScenarioConfig",
    "TopologyConfig",
    "StationConfig",
    "NodeConfig",
    "EdgeConfig",
    "EquipmentConfig",
    "ResolvedConfig",
    # Topology
    "TopologyGraph",
    "StationNode",
    "BufferEdge",
    "CycleDetectedError",
    # Behavior
    "BehaviorConfig",
    "BehaviorOrchestrator",
    "DEFAULT_BEHAVIOR",
    "Phase",
    "PhaseConfig",
    "PhaseContext",
    "PhaseResult",
    "CollectPhase",
    "BreakdownPhase",
    "MicrostopPhase",
    "ExecutePhase",
    "TransformPhase",
    "InspectPhase",
    # Codegen
    "ScenarioGenerator",
    # CLI
    "configure",
    "simulate",
    # Engine
    "SimulationEngine",
    "Equipment",
    # Entry points
    "run_simulation",
    "execute_scenario",
    # Storage
    "save_results",
    "get_db_path",
    "db_connect",
]
