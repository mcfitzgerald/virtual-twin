"""CLI workflow tests for simpy-demo.

Tests the configure and simulate CLI commands that generate
and execute scenario bundles.
"""

import json
from pathlib import Path

import pytest
import yaml

from simpy_demo import configure, simulate


class TestConfigureCommand:
    """Tests for the configure command."""

    def test_configure_generates_bundle(self, config_dir: Path, tmp_path: Path):
        """configure() creates scenario directory with expected files."""
        bundle_path = configure(
            run_name="baseline_8hr",
            config_dir=str(config_dir),
            output_dir=str(tmp_path),
            dry_run=False,
        )

        assert bundle_path is not None
        assert bundle_path.exists()

        # Check expected files
        assert (bundle_path / "scenario.py").exists()
        assert (bundle_path / "config_snapshot.yaml").exists()
        assert (bundle_path / "metadata.json").exists()

    def test_configure_dry_run(self, config_dir: Path, tmp_path: Path):
        """configure(dry_run=True) validates without creating files."""
        result = configure(
            run_name="baseline_8hr",
            config_dir=str(config_dir),
            output_dir=str(tmp_path),
            dry_run=True,
        )

        # Should return None in dry-run mode
        assert result is None

        # No scenario directories should be created
        scenario_dirs = list(tmp_path.glob("baseline_8hr_*"))
        assert len(scenario_dirs) == 0

    def test_config_snapshot_has_all_config(self, config_dir: Path, tmp_path: Path):
        """config_snapshot.yaml captures complete configuration."""
        bundle_path = configure(
            run_name="baseline_8hr",
            config_dir=str(config_dir),
            output_dir=str(tmp_path),
            dry_run=False,
        )

        with open(bundle_path / "config_snapshot.yaml") as f:
            snapshot = yaml.safe_load(f)

        # Check _meta section
        assert "_meta" in snapshot
        assert snapshot["_meta"]["run_name"] == "baseline_8hr"
        # Note: config_hash is in metadata.json, not config_snapshot.yaml

        # Check run section
        assert "run" in snapshot
        assert snapshot["run"]["name"] == "baseline_8hr"
        assert snapshot["run"]["scenario"] == "baseline"
        assert "duration_hours" in snapshot["run"]

        # Check scenario section
        assert "scenario" in snapshot
        assert snapshot["scenario"]["topology"] == "cosmetics_line"

        # Check equipment section
        assert "equipment" in snapshot
        assert "Filler" in snapshot["equipment"]
        assert "Palletizer" in snapshot["equipment"]

    def test_metadata_has_required_fields(self, config_dir: Path, tmp_path: Path):
        """metadata.json has hash, git_commit, version."""
        bundle_path = configure(
            run_name="baseline_8hr",
            config_dir=str(config_dir),
            output_dir=str(tmp_path),
            dry_run=False,
        )

        with open(bundle_path / "metadata.json") as f:
            metadata = json.load(f)

        # Required fields
        assert "scenario_name" in metadata
        assert "generated_at" in metadata
        assert "config_hash" in metadata
        # Hash format is "sha256:<64-char-hex>" = 71 chars total
        assert metadata["config_hash"].startswith("sha256:")
        assert len(metadata["config_hash"]) == 71

        # Git info (may be None if not in git repo)
        assert "git_commit" in metadata
        assert "git_dirty" in metadata

        # Version info
        assert "simpy_demo_version" in metadata
        assert "python_version" in metadata


class TestSimulateCommand:
    """Tests for the simulate command."""

    def test_simulate_runs_bundle(self, config_dir: Path, tmp_path: Path):
        """simulate() executes bundle and produces output."""
        # First create a bundle
        bundle_path = configure(
            run_name="baseline_8hr",
            config_dir=str(config_dir),
            output_dir=str(tmp_path),
            dry_run=False,
        )

        # Modify the config to use short duration for testing
        # We need to modify the original config file temporarily
        # or use a test-specific run config
        # For now, just verify the command works (it will use full duration)

        # Run simulate
        df_ts, df_ev, output_dir = simulate(
            scenario_path=str(bundle_path),
            export=True,
        )

        assert len(df_ts) > 0
        assert len(df_ev) > 0
        assert output_dir.exists()

    def test_simulate_generates_summary_json(self, config_dir: Path, tmp_path: Path):
        """Bundle output includes summary.json."""
        bundle_path = configure(
            run_name="baseline_8hr",
            config_dir=str(config_dir),
            output_dir=str(tmp_path),
            dry_run=False,
        )

        _, _, output_dir = simulate(
            scenario_path=str(bundle_path),
            export=True,
        )

        # Check for summary file
        summary_files = list(output_dir.glob("summary_*.json"))
        assert len(summary_files) == 1

        # Validate summary content
        with open(summary_files[0]) as f:
            summary = json.load(f)

        assert "scenario" in summary
        assert "production" in summary
        assert "economics" in summary
        assert "oee" in summary
