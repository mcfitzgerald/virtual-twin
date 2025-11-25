"""Scenario configuration schemas for what-if experiments."""

from typing import Dict, Optional
from pydantic import BaseModel

from simpy_demo.models import ReliabilityParams, PerformanceParams, QualityParams


class EquipmentParams(BaseModel):
    """Parameters that can vary per scenario (sparse overrides).

    All fields are optional - only specify what you want to override.
    """

    uph: Optional[int] = None
    buffer_capacity: Optional[int] = None
    reliability: Optional[ReliabilityParams] = None
    performance: Optional[PerformanceParams] = None
    quality: Optional[QualityParams] = None


class ScenarioConfig(BaseModel):
    """A scenario = run parameters + equipment parameter overrides.

    Example:
        scenario = ScenarioConfig(
            name="large_buffer_test",
            equipment={
                "Filler": EquipmentParams(buffer_capacity=500)
            }
        )
    """

    name: str
    duration_hours: float = 8.0
    random_seed: Optional[int] = 42
    telemetry_interval_sec: float = 300.0  # 5 minutes default
    equipment: Dict[str, EquipmentParams] = {}  # Overrides by station name
