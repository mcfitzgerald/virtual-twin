"""Layout builder for constructing SimPy structure from topology graph.

Converts a TopologyGraph to SimPy stores and equipment instances,
supporting:
- Multiple upstream sources (merging)
- Multiple downstream targets (branching)
- Conditional routing (quality gates)
- Special nodes (_source, _sink, _reject)
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

import simpy

from virtual_twin.models import MachineConfig, MaterialType, Product
from virtual_twin.topology import TopologyGraph

if TYPE_CHECKING:
    from virtual_twin.aggregation import EventAggregator
    from virtual_twin.equipment import Equipment
    from virtual_twin.loader import SourceConfig

from virtual_twin.behavior import BehaviorOrchestrator, DEFAULT_BEHAVIOR


@dataclass
class RoutingRule:
    """A routing rule for conditional branching.

    Attributes:
        target: Name of target node
        condition: Expression to evaluate (e.g., "not product.is_defective")
        store: SimPy store for this route
    """

    target: str
    condition: Optional[str]
    store: simpy.Store

    def matches(self, product: Product) -> bool:
        """Check if product matches this routing rule.

        Args:
            product: Product to check

        Returns:
            True if product should use this route
        """
        if self.condition is None:
            return True

        # Simple condition evaluation
        # Supports: "product.is_defective", "not product.is_defective"
        condition = self.condition.strip()

        if condition.startswith("not "):
            attr_path = condition[4:].strip()
            return not self._get_attr(product, attr_path)
        else:
            return bool(self._get_attr(product, condition))

    def _get_attr(self, product: Product, path: str) -> Any:
        """Get nested attribute from product.

        Args:
            product: Product instance
            path: Dot-separated path (e.g., "product.is_defective")

        Returns:
            Attribute value (typically bool for conditions)
        """
        # Handle "product.attr" or just "attr"
        parts = path.split(".")
        if parts[0] == "product":
            parts = parts[1:]

        obj: Any = product
        for part in parts:
            obj = getattr(obj, part, False)
        return obj


@dataclass
class NodeConnections:
    """Connection information for a single node.

    Attributes:
        upstream_stores: Dict mapping source name to store
        downstream_routes: List of routing rules for output
        default_downstream: Default store if no condition matches
    """

    upstream_stores: Dict[str, simpy.Store] = field(default_factory=dict)
    downstream_routes: List[RoutingRule] = field(default_factory=list)
    default_downstream: Optional[simpy.Store] = None

    def get_route(self, product: Product) -> simpy.Store:
        """Get the appropriate downstream store for a product.

        Args:
            product: Product to route

        Returns:
            SimPy store to route the product to
        """
        for rule in self.downstream_routes:
            if rule.matches(product):
                return rule.store

        if self.default_downstream:
            return self.default_downstream

        if self.downstream_routes:
            return self.downstream_routes[0].store

        raise ValueError("No downstream route found for product")


@dataclass
class LayoutResult:
    """Result of building a layout from topology graph.

    Attributes:
        machines: Dict mapping node name to Equipment instance
        buffers: Dict mapping buffer name to SimPy store
        connections: Dict mapping node name to NodeConnections
        source_store: The source store (infinite input)
        sink_store: The sink store (infinite output)
        reject_store: The reject store (for defective products)
    """

    machines: Dict[str, "Equipment"]
    buffers: Dict[str, simpy.Store]
    connections: Dict[str, NodeConnections]
    source_store: simpy.Store
    sink_store: simpy.Store
    reject_store: simpy.Store


class LayoutBuilder:
    """Builds SimPy layout from TopologyGraph.

    Supports both linear (backward compatible) and graph-based topologies.
    """

    def __init__(
        self,
        env: simpy.Environment,
        graph: TopologyGraph,
        machine_configs: Dict[str, MachineConfig],
        source_config: Optional["SourceConfig"] = None,
        equipment_factory: Optional[Callable] = None,
        orchestrator: Optional[BehaviorOrchestrator] = None,  # None uses DEFAULT_BEHAVIOR
        event_aggregator: Optional["EventAggregator"] = None,
        debug_events: bool = False,
    ):
        """Initialize layout builder.

        Args:
            env: SimPy environment
            graph: Topology graph to build from
            machine_configs: Dict mapping node name to MachineConfig
            source_config: Source configuration for initial inventory
            equipment_factory: Optional factory for creating Equipment instances
            orchestrator: Behavior orchestrator (uses DEFAULT_BEHAVIOR if None)
            event_aggregator: Optional aggregator for hybrid event storage
            debug_events: If True, populate event_log for full debugging
        """
        self.env = env
        self.graph = graph
        self.machine_configs = machine_configs
        self.source_config = source_config
        self.equipment_factory = equipment_factory
        # Always use an orchestrator (default if not provided)
        self.orchestrator = orchestrator or BehaviorOrchestrator(DEFAULT_BEHAVIOR)
        self.event_aggregator = event_aggregator
        self.debug_events = debug_events

    def build(self) -> LayoutResult:
        """Build the complete SimPy layout.

        Returns:
            LayoutResult with all stores and equipment
        """
        # 1. Create special stores
        source_store = self._create_source_store()
        sink_store = simpy.Store(self.env, capacity=float("inf"))
        reject_store = simpy.Store(self.env, capacity=float("inf"))

        # Map special nodes to their stores
        special_stores = {
            "_source": source_store,
            "_sink": sink_store,
            "_reject": reject_store,
        }

        # 2. Create all buffer stores from edges
        buffers: Dict[str, simpy.Store] = {}
        for edge in self.graph.get_edges():
            # Skip edges where either end is a special node
            # (special nodes use their dedicated stores)
            buffer_name = edge.buffer_name

            # Determine capacity
            capacity: float = float("inf")
            if edge.capacity_override is not None:
                capacity = edge.capacity_override
            elif edge.target not in special_stores:
                # Use target machine's buffer capacity if available
                target_config = self.machine_configs.get(edge.target)
                if target_config:
                    capacity = target_config.buffer_capacity

            buffers[buffer_name] = simpy.Store(self.env, capacity=capacity)

        # 3. Build node connections
        connections: Dict[str, NodeConnections] = {}
        for node in self.graph.get_nodes():
            node_conn = NodeConnections()

            # Upstream connections
            for edge in self.graph.get_upstream(node.name):
                if edge.source in special_stores:
                    node_conn.upstream_stores[edge.source] = special_stores[edge.source]
                else:
                    node_conn.upstream_stores[edge.source] = buffers[edge.buffer_name]

            # Downstream connections
            for edge in self.graph.get_downstream(node.name):
                if edge.target in special_stores:
                    store = special_stores[edge.target]
                else:
                    store = buffers[edge.buffer_name]

                rule = RoutingRule(
                    target=edge.target,
                    condition=edge.condition,
                    store=store,
                )
                node_conn.downstream_routes.append(rule)

                # Set default downstream (first unconditional route)
                if edge.condition is None and node_conn.default_downstream is None:
                    node_conn.default_downstream = store

            connections[node.name] = node_conn

        # 4. Create equipment instances
        machines: Dict[str, "Equipment"] = {}

        # Import here to avoid circular imports
        from virtual_twin.equipment import Equipment

        for node in self.graph.topological_order():
            if node.is_special:
                continue

            config = self.machine_configs.get(node.name)
            if config is None:
                raise ValueError(f"No MachineConfig for node: {node.name}")

            node_conn = connections[node.name]

            # Get primary upstream (for backward compatibility)
            # Use first upstream or source if none
            if node_conn.upstream_stores:
                primary_upstream = list(node_conn.upstream_stores.values())[0]
            else:
                primary_upstream = source_store

            # Get primary downstream
            if node_conn.downstream_routes:
                primary_downstream = node_conn.downstream_routes[0].store
            else:
                primary_downstream = sink_store

            # Check if this node has reject routing
            has_reject_routing = any(
                r.target == "_reject" for r in node_conn.downstream_routes
            )

            # Create equipment using factory or default
            if self.equipment_factory:
                machine = self.equipment_factory(
                    env=self.env,
                    config=config,
                    upstream=primary_upstream,
                    downstream=primary_downstream,
                    reject_store=reject_store if has_reject_routing else None,
                    connections=node_conn,
                    orchestrator=self.orchestrator,
                    event_aggregator=self.event_aggregator,
                    debug_events=self.debug_events,
                )
            else:
                machine = Equipment(
                    env=self.env,
                    config=config,
                    upstream=primary_upstream,
                    downstream=primary_downstream,
                    reject_store=reject_store
                    if config.quality.detection_prob > 0
                    else None,
                    orchestrator=self.orchestrator,
                    event_aggregator=self.event_aggregator,
                    debug_events=self.debug_events,
                )

            machines[node.name] = machine

        return LayoutResult(
            machines=machines,
            buffers=buffers,
            connections=connections,
            source_store=source_store,
            sink_store=sink_store,
            reject_store=reject_store,
        )

    def _create_source_store(self) -> simpy.Store:
        """Create and populate the source store.

        Returns:
            SimPy store pre-filled with initial inventory
        """
        store = simpy.Store(self.env, capacity=float("inf"))

        # Get source parameters
        initial_inventory = 100000
        material_type_str = "None"
        parent_machine = "Raw"

        if self.source_config:
            initial_inventory = self.source_config.initial_inventory
            material_type_str = self.source_config.material_type
            parent_machine = self.source_config.parent_machine

        # Pre-fill with raw material
        for _ in range(initial_inventory):
            store.put(
                Product(
                    type=MaterialType(material_type_str),
                    created_at=0,
                    parent_machine=parent_machine,
                    genealogy=[],
                )
            )

        return store


def build_layout_from_graph(
    env: simpy.Environment,
    graph: TopologyGraph,
    machine_configs: Dict[str, MachineConfig],
    source_config: Optional["SourceConfig"] = None,
) -> Tuple[List["Equipment"], Dict[str, simpy.Store], simpy.Store]:
    """Build layout from graph (convenience function).

    Returns tuple for backward compatibility with engine.py.

    Args:
        env: SimPy environment
        graph: Topology graph
        machine_configs: Dict mapping node name to MachineConfig
        source_config: Source configuration

    Returns:
        Tuple of (machines_list, buffers_dict, reject_store)
    """
    builder = LayoutBuilder(
        env=env,
        graph=graph,
        machine_configs={cfg.name: cfg for cfg in machine_configs.values()}
        if isinstance(machine_configs, dict)
        else {cfg.name: cfg for cfg in machine_configs},
        source_config=source_config,
    )

    result = builder.build()

    # Convert to backward-compatible format
    # Return machines in topological order
    machines_list = [
        result.machines[node.name]
        for node in graph.topological_order()
        if not node.is_special and node.name in result.machines
    ]

    return machines_list, result.buffers, result.reject_store
