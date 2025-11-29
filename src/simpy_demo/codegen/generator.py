"""Scenario generator: creates scenario bundles from resolved configs."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from jinja2 import Environment, FileSystemLoader, PackageLoader

from simpy_demo.loader import ResolvedConfig


class ScenarioGenerator:
    """Generate scenario bundles from resolved configuration."""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        # Use package loader for templates
        try:
            self.jinja_env = Environment(
                loader=PackageLoader("simpy_demo.codegen", "templates"),
                trim_blocks=True,
                lstrip_blocks=True,
            )
        except Exception:
            # Fallback to file system loader
            template_dir = Path(__file__).parent / "templates"
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                trim_blocks=True,
                lstrip_blocks=True,
            )

    def generate_bundle(
        self,
        resolved: ResolvedConfig,
        output_dir: str = "scenarios",
    ) -> Path:
        """Generate a complete scenario bundle.

        Args:
            resolved: Fully resolved configuration
            output_dir: Parent directory for scenario bundles

        Returns:
            Path to the created bundle directory
        """
        # 1. Create bundle directory with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        bundle_name = f"{resolved.run.name}_{timestamp}"
        bundle_path = Path(output_dir) / bundle_name
        bundle_path.mkdir(parents=True, exist_ok=True)

        # 2. Generate config snapshot
        config_snapshot = self._create_config_snapshot(resolved)
        config_hash = self._compute_hash(config_snapshot)

        # 3. Generate metadata
        metadata = self._create_metadata(resolved, config_hash, timestamp)

        # 4. Write config_snapshot.yaml
        snapshot_path = bundle_path / "config_snapshot.yaml"
        with open(snapshot_path, "w") as f:
            f.write("# Auto-generated frozen configuration\n")
            f.write(
                f"# DO NOT EDIT - regenerate with: "
                f"python -m simpy_demo configure --run {resolved.run.name}\n\n"
            )
            yaml.dump(config_snapshot, f, default_flow_style=False, sort_keys=False)

        # 5. Write metadata.json
        metadata_path = bundle_path / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2, default=str)

        # 6. Generate scenario.py
        scenario_py = self._generate_scenario_py(resolved, config_hash, timestamp)
        scenario_path = bundle_path / "scenario.py"
        with open(scenario_path, "w") as f:
            f.write(scenario_py)

        # Make scenario.py executable
        scenario_path.chmod(0o755)

        return bundle_path

    def _create_config_snapshot(self, resolved: ResolvedConfig) -> Dict[str, Any]:
        """Create a frozen config snapshot dict."""
        snapshot: Dict[str, Any] = {
            "_meta": {
                "generated_at": datetime.now().isoformat(),
                "run_name": resolved.run.name,
                "config_dir": str(self.config_dir),
            },
            "run": {
                "name": resolved.run.name,
                "scenario": resolved.run.scenario,
                "product": resolved.run.product,
                "duration_hours": resolved.run.duration_hours,
                "random_seed": resolved.run.random_seed,
                "telemetry_interval_sec": resolved.run.telemetry_interval_sec,
                "start_time": resolved.run.start_time.isoformat()
                if resolved.run.start_time
                else None,
            },
            "scenario": {
                "name": resolved.scenario.name,
                "topology": resolved.scenario.topology,
                "equipment": resolved.scenario.equipment,
                "overrides": resolved.scenario.overrides,
                "behavior": resolved.scenario.behavior,
            },
            "topology": {
                "name": resolved.topology.name,
                "source": resolved.topology.source,
            },
        }

        # Add stations or nodes/edges based on topology type
        if resolved.topology.is_graph_topology:
            snapshot["topology"]["nodes"] = [
                {
                    "name": n.name,
                    "batch_in": n.batch_in,
                    "output_type": n.output_type.value,
                    "equipment_ref": n.equipment_ref,
                    "behavior_ref": n.behavior_ref,
                }
                for n in resolved.topology.nodes
            ]
            snapshot["topology"]["edges"] = [
                {
                    "source": e.source,
                    "target": e.target,
                    "capacity_override": e.capacity_override,
                    "condition": e.condition,
                }
                for e in resolved.topology.edges
            ]
        else:
            snapshot["topology"]["stations"] = [
                {
                    "name": s.name,
                    "batch_in": s.batch_in,
                    "output_type": s.output_type.value,
                }
                for s in resolved.topology.stations
            ]

        # Equipment configs
        snapshot["equipment"] = {}
        for name, equip in resolved.equipment.items():
            equip_dict: Dict[str, Any] = {
                "name": equip.name,
                "uph": equip.uph,
                "buffer_capacity": equip.buffer_capacity,
            }
            if equip.reliability:
                equip_dict["reliability"] = {
                    "mtbf_min": equip.reliability.mtbf_min,
                    "mttr_min": equip.reliability.mttr_min,
                }
            if equip.performance:
                equip_dict["performance"] = {
                    "jam_prob": equip.performance.jam_prob,
                    "jam_time_sec": equip.performance.jam_time_sec,
                }
            if equip.quality:
                equip_dict["quality"] = {
                    "defect_rate": equip.quality.defect_rate,
                    "detection_prob": equip.quality.detection_prob,
                }
            if equip.cost_rates:
                equip_dict["cost_rates"] = {
                    "labor_per_hour": equip.cost_rates.labor_per_hour,
                    "energy_per_hour": equip.cost_rates.energy_per_hour,
                    "overhead_per_hour": equip.cost_rates.overhead_per_hour,
                }
            snapshot["equipment"][name] = equip_dict

        # Source config
        if resolved.source:
            snapshot["source"] = {
                "name": resolved.source.name,
                "description": resolved.source.description,
                "initial_inventory": resolved.source.initial_inventory,
                "material_type": resolved.source.material_type,
                "parent_machine": resolved.source.parent_machine,
            }

        # Product config
        if resolved.product:
            snapshot["product"] = {
                "name": resolved.product.name,
                "description": resolved.product.description,
                "size_oz": resolved.product.size_oz,
                "net_weight_g": resolved.product.net_weight_g,
                "units_per_case": resolved.product.units_per_case,
                "cases_per_pallet": resolved.product.cases_per_pallet,
                "material_cost": resolved.product.material_cost,
                "selling_price": resolved.product.selling_price,
            }

        # Constants
        if resolved.constants:
            snapshot["constants"] = resolved.constants.constants

        # Behavior config
        if resolved.behavior:
            snapshot["behavior"] = {
                "name": resolved.behavior.name,
                "description": resolved.behavior.description,
                "phases": [
                    {
                        "name": p.name,
                        "handler": p.handler,
                        "enabled": p.enabled,
                        "params": p.params,
                    }
                    for p in resolved.behavior.phases
                ],
            }

        return snapshot

    def _create_metadata(
        self, resolved: ResolvedConfig, config_hash: str, timestamp: str
    ) -> Dict[str, Any]:
        """Create metadata dict for the scenario bundle."""
        source_configs: Dict[str, Any] = {
            "run": f"config/runs/{resolved.run.name}.yaml",
            "scenario": f"config/scenarios/{resolved.scenario.name}.yaml",
            "topology": f"config/topologies/{resolved.topology.name}.yaml",
            "equipment": [
                f"config/equipment/{name.lower()}.yaml"
                for name in resolved.equipment.keys()
            ],
        }

        if resolved.product:
            source_configs["product"] = f"config/products/{resolved.product.name}.yaml"

        metadata: Dict[str, Any] = {
            "scenario_name": resolved.run.name,
            "generated_at": datetime.now().isoformat(),
            "config_hash": config_hash,
            "git_commit": self._get_git_commit(),
            "git_dirty": self._is_git_dirty(),
            "cli_command": f"python -m simpy_demo configure --run {resolved.run.name}",
            "simpy_demo_version": self._get_version(),
            "python_version": self._get_python_version(),
            "source_configs": source_configs,
        }

        return metadata

    def _generate_scenario_py(
        self, resolved: ResolvedConfig, config_hash: str, timestamp: str
    ) -> str:
        """Generate the scenario.py runner script."""
        try:
            template = self.jinja_env.get_template("scenario.py.j2")
            return template.render(
                run_name=resolved.run.name,
                timestamp=timestamp,
                config_hash=config_hash,
                git_commit=self._get_git_commit() or "unknown",
            )
        except Exception:
            # Fallback to inline template if Jinja template not found
            return self._generate_scenario_py_inline(resolved, config_hash, timestamp)

    def _generate_scenario_py_inline(
        self, resolved: ResolvedConfig, config_hash: str, timestamp: str
    ) -> str:
        """Generate scenario.py using inline template (fallback)."""
        git_commit = self._get_git_commit() or "unknown"
        return f'''#!/usr/bin/env python3
"""
Scenario: {resolved.run.name}
Generated: {timestamp}
Config Hash: {config_hash[:16]}...
Git Commit: {git_commit}
"""

from pathlib import Path

from simpy_demo.simulation.runtime import execute_scenario

SCENARIO_DIR = Path(__file__).parent
CONFIG_PATH = SCENARIO_DIR / "config_snapshot.yaml"


def main():
    """Run this scenario."""
    execute_scenario(CONFIG_PATH)


if __name__ == "__main__":
    main()
'''

    def _compute_hash(self, data: Dict[str, Any]) -> str:
        """Compute SHA256 hash of config data."""
        # Remove _meta section for hashing (contains timestamp)
        hashable = {k: v for k, v in data.items() if k != "_meta"}
        json_str = json.dumps(hashable, sort_keys=True, default=str)
        return f"sha256:{hashlib.sha256(json_str.encode()).hexdigest()}"

    def _get_git_commit(self) -> Optional[str]:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _is_git_dirty(self) -> bool:
        """Check if working directory has uncommitted changes."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return len(result.stdout.strip()) > 0
        except Exception:
            pass
        return False

    def _get_version(self) -> str:
        """Get simpy-demo version."""
        try:
            from importlib.metadata import version

            return version("simpy-demo")
        except Exception:
            return "unknown"

    def _get_python_version(self) -> str:
        """Get Python version."""
        import sys

        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
