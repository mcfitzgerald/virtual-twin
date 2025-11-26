"""Graph-based topology for production line DAG structure.

Supports:
- Branching (one station feeding multiple stations)
- Merging (multiple stations feeding one station)
- Conditional routing (quality gates)
- Rework loops (with cycle detection)
- Special nodes: _source, _sink, _reject
"""

from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Set

from simpy_demo.models import MaterialType


@dataclass
class StationNode:
    """A station or routing node in the topology graph.

    Attributes:
        name: Unique identifier for this node
        batch_in: Number of input items per cycle (default 1)
        output_type: Type of material produced (TUBE, CASE, PALLET, NONE)
        equipment_ref: Reference to equipment config name (optional)
        behavior_ref: Reference to behavior config name (optional, for future use)
    """

    name: str
    batch_in: int = 1
    output_type: MaterialType = MaterialType.NONE
    equipment_ref: Optional[str] = None
    behavior_ref: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate node configuration."""
        if self.batch_in < 1:
            raise ValueError(f"batch_in must be >= 1, got {self.batch_in}")

    @property
    def is_special(self) -> bool:
        """Check if this is a special node (_source, _sink, _reject)."""
        return self.name.startswith("_")


@dataclass
class BufferEdge:
    """A connection (buffer) between two nodes in the topology graph.

    Attributes:
        source: Name of source node
        target: Name of target node
        capacity_override: Buffer capacity (None = use equipment default)
        condition: Expression for conditional routing (e.g., "not product.is_defective")
    """

    source: str
    target: str
    capacity_override: Optional[int] = None
    condition: Optional[str] = None

    @property
    def buffer_name(self) -> str:
        """Generate buffer name from source and target."""
        return f"Buf_{self.source}_to_{self.target}"

    def __post_init__(self) -> None:
        """Validate edge configuration."""
        if not self.source:
            raise ValueError("Edge source cannot be empty")
        if not self.target:
            raise ValueError("Edge target cannot be empty")
        if self.source == self.target:
            raise ValueError(f"Self-loop not allowed: {self.source}")


class CycleDetectedError(Exception):
    """Raised when a cycle is detected in the topology graph."""

    pass


class TopologyGraph:
    """DAG-based topology graph for production line structure.

    Provides:
    - Node and edge management
    - Upstream/downstream traversal
    - Topological ordering
    - Cycle detection
    - Validation

    Special nodes:
    - _source: Infinite raw material source
    - _sink: Output sink (completed products)
    - _reject: Rejected/defective products sink
    """

    # Reserved special node names
    SPECIAL_NODES = {"_source", "_sink", "_reject"}

    def __init__(self) -> None:
        """Initialize empty topology graph."""
        self._nodes: Dict[str, StationNode] = {}
        self._edges: List[BufferEdge] = []

        # Adjacency lists for traversal
        self._outgoing: Dict[str, List[BufferEdge]] = {}
        self._incoming: Dict[str, List[BufferEdge]] = {}

    def add_node(self, node: StationNode) -> None:
        """Add a station node to the graph.

        Args:
            node: The station node to add

        Raises:
            ValueError: If node with same name already exists
        """
        if node.name in self._nodes:
            raise ValueError(f"Node already exists: {node.name}")

        self._nodes[node.name] = node
        self._outgoing[node.name] = []
        self._incoming[node.name] = []

    def add_edge(self, edge: BufferEdge) -> None:
        """Add a buffer edge between two nodes.

        Args:
            edge: The buffer edge to add

        Raises:
            ValueError: If source or target node doesn't exist (except special nodes)
        """
        # Special nodes are implicitly created
        for node_name in [edge.source, edge.target]:
            if node_name not in self._nodes:
                if node_name in self.SPECIAL_NODES:
                    # Auto-create special nodes
                    self.add_node(
                        StationNode(
                            name=node_name,
                            output_type=MaterialType.NONE,
                        )
                    )
                else:
                    raise ValueError(f"Node not found: {node_name}")

        self._edges.append(edge)
        self._outgoing[edge.source].append(edge)
        self._incoming[edge.target].append(edge)

    def get_node(self, name: str) -> Optional[StationNode]:
        """Get a node by name."""
        return self._nodes.get(name)

    def get_nodes(self) -> List[StationNode]:
        """Get all nodes (excluding special nodes)."""
        return [n for n in self._nodes.values() if not n.is_special]

    def get_all_nodes(self) -> List[StationNode]:
        """Get all nodes including special nodes."""
        return list(self._nodes.values())

    def get_edges(self) -> List[BufferEdge]:
        """Get all edges."""
        return list(self._edges)

    def get_downstream(self, station: str) -> List[BufferEdge]:
        """Get all outgoing edges from a station.

        Args:
            station: Name of the station

        Returns:
            List of edges leaving this station
        """
        return self._outgoing.get(station, [])

    def get_upstream(self, station: str) -> List[BufferEdge]:
        """Get all incoming edges to a station.

        Args:
            station: Name of the station

        Returns:
            List of edges entering this station
        """
        return self._incoming.get(station, [])

    def get_downstream_nodes(self, station: str) -> List[str]:
        """Get names of all downstream stations."""
        return [e.target for e in self.get_downstream(station)]

    def get_upstream_nodes(self, station: str) -> List[str]:
        """Get names of all upstream stations."""
        return [e.source for e in self.get_upstream(station)]

    def topological_order(self) -> Iterator[StationNode]:
        """Iterate over nodes in topological order (Kahn's algorithm).

        Yields:
            Nodes in dependency order (sources first, sinks last)

        Raises:
            CycleDetectedError: If the graph contains a cycle
        """
        # Calculate in-degrees
        in_degree: Dict[str, int] = {name: 0 for name in self._nodes}
        for edge in self._edges:
            in_degree[edge.target] += 1

        # Start with nodes having no incoming edges
        queue = deque(
            [name for name, degree in in_degree.items() if degree == 0]
        )

        visited = 0
        while queue:
            name = queue.popleft()
            node = self._nodes[name]
            visited += 1
            yield node

            for edge in self._outgoing[name]:
                in_degree[edge.target] -= 1
                if in_degree[edge.target] == 0:
                    queue.append(edge.target)

        if visited != len(self._nodes):
            raise CycleDetectedError(
                "Topology graph contains a cycle. "
                f"Visited {visited} of {len(self._nodes)} nodes."
            )

    def validate(self) -> List[str]:
        """Validate the topology graph.

        Returns:
            List of validation errors (empty if valid)
        """
        errors: List[str] = []

        # 1. Check for source connectivity
        source_edges = self._outgoing.get("_source", [])
        if not source_edges:
            errors.append("No edges from _source - line has no input")

        # 2. Check for sink connectivity
        sink_edges = self._incoming.get("_sink", [])
        if not sink_edges:
            errors.append("No edges to _sink - line has no output")

        # 3. Check for orphan nodes (no connections)
        for name, node in self._nodes.items():
            if node.is_special:
                continue
            if not self._incoming[name] and not self._outgoing[name]:
                errors.append(f"Orphan node with no connections: {name}")

        # 4. Check for cycles
        try:
            list(self.topological_order())
        except CycleDetectedError as e:
            errors.append(str(e))

        # 5. Check conditional edge completeness
        # If any edge has a condition, all outgoing edges from that source should
        for source_name in self._nodes:
            outgoing = self._outgoing.get(source_name, [])
            conditional_edges = [e for e in outgoing if e.condition]
            if conditional_edges and len(conditional_edges) != len(outgoing):
                errors.append(
                    f"Node {source_name} has mixed conditional/unconditional "
                    f"outgoing edges. All or none should have conditions."
                )

        return errors

    def is_valid(self) -> bool:
        """Check if the topology is valid."""
        return len(self.validate()) == 0

    def find_path(
        self, start: str, end: str, visited: Optional[Set[str]] = None
    ) -> Optional[List[str]]:
        """Find a path between two nodes using DFS.

        Args:
            start: Starting node name
            end: Ending node name
            visited: Set of already visited nodes (for recursion)

        Returns:
            List of node names representing path, or None if no path exists
        """
        if visited is None:
            visited = set()

        if start == end:
            return [start]

        if start in visited:
            return None

        visited.add(start)

        for edge in self.get_downstream(start):
            path = self.find_path(edge.target, end, visited)
            if path:
                return [start] + path

        return None

    def has_conditional_routing(self) -> bool:
        """Check if any edges have conditional routing."""
        return any(e.condition for e in self._edges)

    @classmethod
    def from_linear(
        cls,
        stations: List[Dict[str, Any]],
        source_name: str = "_source",
        sink_name: str = "_sink",
    ) -> "TopologyGraph":
        """Create a graph from a linear list of stations (backward compatibility).

        Args:
            stations: List of station dicts with name, batch_in, output_type
            source_name: Name of source node
            sink_name: Name of sink node

        Returns:
            TopologyGraph with linear structure
        """
        graph = cls()

        # Add nodes
        for station in stations:
            node = StationNode(
                name=station["name"],
                batch_in=station.get("batch_in", 1),
                output_type=MaterialType(station.get("output_type", "None")),
                equipment_ref=station.get("equipment_ref", station["name"]),
            )
            graph.add_node(node)

        # Add edges (linear chain)
        prev_name = source_name
        for station in stations:
            graph.add_edge(BufferEdge(source=prev_name, target=station["name"]))
            prev_name = station["name"]

        # Connect last station to sink
        graph.add_edge(BufferEdge(source=prev_name, target=sink_name))

        return graph

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"TopologyGraph(nodes={len(self._nodes)}, edges={len(self._edges)})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert graph to dictionary for serialization."""
        return {
            "nodes": [
                {
                    "name": n.name,
                    "batch_in": n.batch_in,
                    "output_type": n.output_type.value,
                    "equipment_ref": n.equipment_ref,
                    "behavior_ref": n.behavior_ref,
                }
                for n in self._nodes.values()
                if not n.is_special
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "capacity_override": e.capacity_override,
                    "condition": e.condition,
                }
                for e in self._edges
            ],
        }
