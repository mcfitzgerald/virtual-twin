"""YAML configuration loader with name-based resolution."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from simpy_demo.models import (
    CostRates,
    MachineConfig,
    MaterialType,
    PerformanceParams,
    ProductConfig,
    QualityParams,
    ReliabilityParams,
)


# --- New config dataclasses for Phase 1 ---


@dataclass
class DefaultsConfig:
    """Global defaults loaded from config/defaults.yaml."""

    time: Dict[str, Any] = field(default_factory=dict)
    simulation: Dict[str, Any] = field(default_factory=dict)
    equipment: Dict[str, Any] = field(default_factory=dict)
    product: Dict[str, Any] = field(default_factory=dict)
    source: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConstantsConfig:
    """Named constants loaded from config/constants.yaml."""

    constants: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a constant value by name."""
        return self.constants.get(key, default)


@dataclass
class SourceConfig:
    """Source configuration for raw material input."""

    name: str
    description: str = ""
    initial_inventory: int = 100000
    material_type: str = "None"
    parent_machine: str = "Raw"


class ConfigLoader:
    """Loads and resolves YAML configuration files."""

    def __init__(self, config_dir: Path | str = "config"):
        self.config_dir = Path(config_dir)
        # Load global defaults and constants on init
        self.defaults = self.load_defaults()
        self.constants = self.load_constants()

    def load_defaults(self) -> DefaultsConfig:
        """Load global defaults from config/defaults.yaml."""
        path = self.config_dir / "defaults.yaml"
        if not path.exists():
            return DefaultsConfig()
        data = self._load_yaml(path)
        return DefaultsConfig(
            time=data.get("time", {}),
            simulation=data.get("simulation", {}),
            equipment=data.get("equipment", {}),
            product=data.get("product", {}),
            source=data.get("source", {}),
        )

    def load_constants(self) -> ConstantsConfig:
        """Load named constants from config/constants.yaml."""
        path = self.config_dir / "constants.yaml"
        if not path.exists():
            return ConstantsConfig()
        data = self._load_yaml(path)
        return ConstantsConfig(constants=data.get("constants", {}))

    def load_source(self, name: str) -> SourceConfig:
        """Load a source configuration by name."""
        path = self.config_dir / "sources" / f"{name}.yaml"
        data = self._load_yaml(path)
        # Get defaults from defaults.yaml
        src_defaults = self.defaults.source
        return SourceConfig(
            name=data["name"],
            description=data.get("description", ""),
            initial_inventory=data.get(
                "initial_inventory", src_defaults.get("initial_inventory", 100000)
            ),
            material_type=data.get(
                "material_type", src_defaults.get("material_type", "None")
            ),
            parent_machine=data.get(
                "parent_machine", src_defaults.get("parent_machine", "Raw")
            ),
        )

    def load_run(self, name: str) -> "RunConfig":
        """Load a run configuration by name."""
        path = self.config_dir / "runs" / f"{name}.yaml"
        data = self._load_yaml(path)

        # Parse start_time if provided
        start_time = None
        if data.get("start_time"):
            start_time = datetime.fromisoformat(data["start_time"])

        # Use defaults from defaults.yaml
        sim_defaults = self.defaults.simulation
        return RunConfig(
            name=data["name"],
            scenario=data["scenario"],
            product=data.get("product"),  # Optional product reference
            duration_hours=data.get(
                "duration_hours", sim_defaults.get("duration_hours", 8.0)
            ),
            random_seed=data.get("random_seed", sim_defaults.get("random_seed", 42)),
            telemetry_interval_sec=data.get(
                "telemetry_interval_sec",
                sim_defaults.get("telemetry_interval_sec", 300.0),
            ),
            start_time=start_time,
        )

    def load_scenario(self, name: str) -> "ScenarioConfig":
        """Load a scenario configuration by name."""
        path = self.config_dir / "scenarios" / f"{name}.yaml"
        data = self._load_yaml(path)
        return ScenarioConfig(
            name=data["name"],
            topology=data["topology"],
            equipment=data.get("equipment", []),
            overrides=data.get("overrides", {}),
        )

    def load_topology(self, name: str) -> "TopologyConfig":
        """Load a topology configuration by name."""
        path = self.config_dir / "topologies" / f"{name}.yaml"
        data = self._load_yaml(path)
        stations = [
            StationConfig(
                name=s["name"],
                batch_in=s.get("batch_in", 1),
                output_type=MaterialType(s.get("output_type", "None")),
            )
            for s in data.get("stations", [])
        ]
        return TopologyConfig(
            name=data["name"],
            source=data.get("source", "infinite_raw"),  # Default source
            materials=data.get("materials", "cosmetics"),  # Default materials
            stations=stations,
        )

    def load_equipment(self, name: str) -> "EquipmentConfig":
        """Load an equipment configuration by name."""
        # Try lowercase filename first, then original
        path = self.config_dir / "equipment" / f"{name.lower()}.yaml"
        if not path.exists():
            path = self.config_dir / "equipment" / f"{name}.yaml"
        data = self._load_yaml(path)
        return self._parse_equipment(data)

    def load_materials(self, name: str) -> "MaterialsConfig":
        """Load a materials configuration by name."""
        path = self.config_dir / "materials" / f"{name}.yaml"
        data = self._load_yaml(path)
        return MaterialsConfig(name=data["name"], types=data.get("types", {}))

    def load_product(self, name: str) -> ProductConfig:
        """Load a product configuration by name."""
        path = self.config_dir / "products" / f"{name}.yaml"
        data = self._load_yaml(path)
        # Use defaults from defaults.yaml
        prod_defaults = self.defaults.product
        return ProductConfig(
            name=data["name"],
            description=data.get("description", ""),
            size_oz=data.get("size_oz", 0.0),
            units_per_case=data.get(
                "units_per_case", prod_defaults.get("units_per_case", 12)
            ),
            cases_per_pallet=data.get(
                "cases_per_pallet", prod_defaults.get("cases_per_pallet", 60)
            ),
            material_cost=data.get(
                "material_cost", prod_defaults.get("material_cost", 150.0)
            ),
            selling_price=data.get(
                "selling_price", prod_defaults.get("selling_price", 450.0)
            ),
        )

    def resolve_run(self, run_name: str) -> "ResolvedConfig":
        """Fully resolve a run config into all its components."""
        run = self.load_run(run_name)
        scenario = self.load_scenario(run.scenario)
        topology = self.load_topology(scenario.topology)

        # Load source config from topology reference
        source = self.load_source(topology.source)

        # Load materials config from topology reference
        materials = self.load_materials(topology.materials)

        # Load product config if specified
        product = None
        if run.product:
            product = self.load_product(run.product)

        # Load equipment configs for each station
        equipment_configs: Dict[str, EquipmentConfig] = {}
        for equip_name in scenario.equipment:
            equipment_configs[equip_name] = self.load_equipment(equip_name)

        # Apply scenario overrides
        for equip_name, overrides in scenario.overrides.items():
            if equip_name in equipment_configs:
                equipment_configs[equip_name] = self._apply_overrides(
                    equipment_configs[equip_name], overrides
                )

        return ResolvedConfig(
            run=run,
            scenario=scenario,
            topology=topology,
            equipment=equipment_configs,
            product=product,
            source=source,
            constants=self.constants,
            materials=materials,
        )

    def build_machine_configs(self, resolved: "ResolvedConfig") -> List[MachineConfig]:
        """Build MachineConfig objects from resolved configuration."""
        configs = []
        for station in resolved.topology.stations:
            equip = resolved.equipment.get(station.name)
            if equip is None:
                raise ValueError(f"No equipment config for station: {station.name}")

            config = MachineConfig(
                name=station.name,
                uph=equip.uph,
                batch_in=station.batch_in,
                output_type=station.output_type,
                buffer_capacity=equip.buffer_capacity,
                reliability=equip.reliability or ReliabilityParams(),
                performance=equip.performance or PerformanceParams(),
                quality=equip.quality or QualityParams(),
                cost_rates=equip.cost_rates or CostRates(),
            )
            configs.append(config)
        return configs

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load a YAML file."""
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path) as f:
            return yaml.safe_load(f) or {}

    def _parse_equipment(self, data: Dict[str, Any]) -> "EquipmentConfig":
        """Parse equipment data into EquipmentConfig."""
        reliability = None
        if "reliability" in data and data["reliability"]:
            rel = data["reliability"]
            # Filter out None values, let Pydantic use defaults
            rel_kwargs = {}
            if rel.get("mtbf_min") is not None:
                rel_kwargs["mtbf_min"] = rel["mtbf_min"]
            if rel.get("mttr_min") is not None:
                rel_kwargs["mttr_min"] = rel["mttr_min"]
            reliability = ReliabilityParams(**rel_kwargs)

        performance = None
        if "performance" in data and data["performance"]:
            perf = data["performance"]
            perf_kwargs = {}
            if perf.get("jam_prob") is not None:
                perf_kwargs["jam_prob"] = perf["jam_prob"]
            if perf.get("jam_time_sec") is not None:
                perf_kwargs["jam_time_sec"] = perf["jam_time_sec"]
            performance = PerformanceParams(**perf_kwargs)

        quality = None
        if "quality" in data and data["quality"]:
            qual = data["quality"]
            qual_kwargs = {}
            if qual.get("defect_rate") is not None:
                qual_kwargs["defect_rate"] = qual["defect_rate"]
            if qual.get("detection_prob") is not None:
                qual_kwargs["detection_prob"] = qual["detection_prob"]
            quality = QualityParams(**qual_kwargs)

        cost_rates = None
        if "cost_rates" in data and data["cost_rates"]:
            cr = data["cost_rates"]
            cr_kwargs = {}
            if cr.get("labor_per_hour") is not None:
                cr_kwargs["labor_per_hour"] = cr["labor_per_hour"]
            if cr.get("energy_per_hour") is not None:
                cr_kwargs["energy_per_hour"] = cr["energy_per_hour"]
            if cr.get("overhead_per_hour") is not None:
                cr_kwargs["overhead_per_hour"] = cr["overhead_per_hour"]
            cost_rates = CostRates(**cr_kwargs)

        # Use defaults from defaults.yaml
        equip_defaults = self.defaults.equipment
        return EquipmentConfig(
            name=data["name"],
            uph=data.get("uph", equip_defaults.get("uph", 10000)),
            buffer_capacity=data.get(
                "buffer_capacity", equip_defaults.get("buffer_capacity", 50)
            ),
            reliability=reliability,
            performance=performance,
            quality=quality,
            cost_rates=cost_rates,
        )

    def _apply_overrides(
        self, base: "EquipmentConfig", overrides: Dict[str, Any]
    ) -> "EquipmentConfig":
        """Apply overrides to an equipment config."""
        data = {
            "name": base.name,
            "uph": overrides.get("uph", base.uph),
            "buffer_capacity": overrides.get("buffer_capacity", base.buffer_capacity),
        }

        # Handle nested overrides
        if base.reliability or "reliability" in overrides:
            rel_base = base.reliability or ReliabilityParams()
            rel_over = overrides.get("reliability", {})
            data["reliability"] = {
                "mtbf_min": rel_over.get("mtbf_min", rel_base.mtbf_min),
                "mttr_min": rel_over.get("mttr_min", rel_base.mttr_min),
            }

        if base.performance or "performance" in overrides:
            perf_base = base.performance or PerformanceParams()
            perf_over = overrides.get("performance", {})
            data["performance"] = {
                "jam_prob": perf_over.get("jam_prob", perf_base.jam_prob),
                "jam_time_sec": perf_over.get("jam_time_sec", perf_base.jam_time_sec),
            }

        if base.quality or "quality" in overrides:
            qual_base = base.quality or QualityParams()
            qual_over = overrides.get("quality", {})
            data["quality"] = {
                "defect_rate": qual_over.get("defect_rate", qual_base.defect_rate),
                "detection_prob": qual_over.get(
                    "detection_prob", qual_base.detection_prob
                ),
            }

        return self._parse_equipment(data)


# --- Config dataclasses ---


@dataclass
class RunConfig:
    """Run-level configuration."""

    name: str
    scenario: str
    product: Optional[str] = None  # Reference to product config
    duration_hours: float = 8.0
    random_seed: Optional[int] = 42
    telemetry_interval_sec: float = 300.0
    start_time: Optional[datetime] = None  # None = use datetime.now()


@dataclass
class ScenarioConfig:
    """Scenario configuration."""

    name: str
    topology: str
    equipment: List[str] = field(default_factory=list)
    overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class StationConfig:
    """Station in a topology."""

    name: str
    batch_in: int = 1
    output_type: MaterialType = MaterialType.NONE


@dataclass
class TopologyConfig:
    """Topology configuration."""

    name: str
    source: str = "infinite_raw"  # Reference to config/sources/*.yaml
    materials: str = "cosmetics"  # Reference to config/materials/*.yaml
    stations: List[StationConfig] = field(default_factory=list)


@dataclass
class EquipmentConfig:
    """Equipment parameters."""

    name: str
    uph: int = 10000
    buffer_capacity: int = 50
    reliability: Optional[ReliabilityParams] = None
    performance: Optional[PerformanceParams] = None
    quality: Optional[QualityParams] = None
    cost_rates: Optional[CostRates] = None


@dataclass
class MaterialsConfig:
    """Materials configuration."""

    name: str
    types: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class ResolvedConfig:
    """Fully resolved configuration ready for simulation."""

    run: RunConfig
    scenario: ScenarioConfig
    topology: TopologyConfig
    equipment: Dict[str, EquipmentConfig] = field(default_factory=dict)
    product: Optional[ProductConfig] = None
    source: Optional[SourceConfig] = None
    constants: Optional[ConstantsConfig] = None
    materials: Optional["MaterialsConfig"] = None
