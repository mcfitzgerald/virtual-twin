"""Configure command: Generate a standalone scenario bundle from YAML configs."""

from pathlib import Path
from typing import Optional

from virtual_twin.codegen import ScenarioGenerator
from virtual_twin.loader import ConfigLoader


def configure(
    run_name: str,
    config_dir: str = "config",
    output_dir: str = "scenarios",
    dry_run: bool = False,
) -> Optional[Path]:
    """Generate a standalone scenario bundle from YAML configs.

    Args:
        run_name: Name of the run config (without .yaml extension)
        config_dir: Path to config directory
        output_dir: Output directory for scenario bundles
        dry_run: If True, validate config without generating files

    Returns:
        Path to the generated scenario bundle directory, or None if dry_run
    """
    # 1. Load and resolve all configs
    loader = ConfigLoader(config_dir)
    resolved = loader.resolve_run(run_name)

    print(f"Resolving configuration for run: {run_name}")
    print(f"  Scenario: {resolved.scenario.name}")
    print(f"  Topology: {resolved.topology.name}")
    print(f"  Equipment: {', '.join(resolved.equipment.keys())}")
    if resolved.product:
        print(f"  Product: {resolved.product.name}")

    if dry_run:
        print("\n[dry-run] Configuration is valid. No files generated.")
        return None

    # 2. Generate scenario bundle
    generator = ScenarioGenerator(config_dir=config_dir)
    bundle_path = generator.generate_bundle(
        resolved=resolved,
        output_dir=output_dir,
    )

    print(f"\nScenario bundle created: {bundle_path}")
    print("  scenario.py          - Lightweight runner script")
    print("  config_snapshot.yaml - Frozen configuration")
    print("  metadata.json        - Generation metadata")
    print("\nTo run this scenario:")
    print(f"  python -m virtual_twin simulate --scenario {bundle_path}")

    return bundle_path
