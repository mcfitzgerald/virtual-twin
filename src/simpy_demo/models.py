"""Pydantic schemas for simulation models."""

import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MaterialType(str, Enum):
    """Material types in the production hierarchy."""

    TUBE = "Tube"
    CASE = "Case"
    PALLET = "Pallet"
    NONE = "None"


class Product(BaseModel):
    """A physical item flowing through the production line."""

    uid: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: MaterialType
    created_at: float
    parent_machine: str
    is_defective: bool = False
    genealogy: List[str] = Field(default_factory=list)
    telemetry: Dict[str, Any] = Field(default_factory=dict)


# --- Grouped parameter sub-models ---


class ReliabilityParams(BaseModel):
    """Availability loss parameters (MTBF/MTTR)."""

    mtbf_min: Optional[float] = None  # Mean Time Between Failures (minutes)
    mttr_min: float = 60.0  # Mean Time To Repair (minutes)


class PerformanceParams(BaseModel):
    """Performance loss parameters (microstops/jams)."""

    jam_prob: float = 0.0  # Probability per cycle
    jam_time_sec: float = 10.0  # Fixed jam clearance time


class QualityParams(BaseModel):
    """Quality loss parameters (defects/inspection)."""

    defect_rate: float = 0.0  # Probability of creating defect
    detection_prob: float = 0.0  # Inspection accuracy


class CostRates(BaseModel):
    """Cost rates for conversion cost calculation (per hour)."""

    labor_per_hour: float = 25.0  # $/hr operator cost
    energy_per_hour: float = 5.0  # $/hr electricity
    overhead_per_hour: float = 10.0  # $/hr maintenance, depreciation

    @property
    def total_per_hour(self) -> float:
        """Total cost rate per hour."""
        return self.labor_per_hour + self.energy_per_hour + self.overhead_per_hour


class ProductConfig(BaseModel):
    """Product/SKU configuration with economic attributes."""

    name: str
    description: str = ""

    # Physical attributes
    size_oz: float = 0.0
    net_weight_g: float = 0.0  # Net weight per unit in grams
    units_per_case: int = 12
    cases_per_pallet: int = 60

    # Economic attributes (per pallet)
    material_cost: float = 150.0  # $ per pallet of raw materials
    selling_price: float = 450.0  # $ per pallet


class MachineConfig(BaseModel):
    """Complete machine configuration with grouped parameters."""

    name: str
    uph: int  # Units Per Hour
    batch_in: int = 1
    output_type: MaterialType = MaterialType.NONE
    buffer_capacity: int = 50

    reliability: ReliabilityParams = Field(default_factory=ReliabilityParams)
    performance: PerformanceParams = Field(default_factory=PerformanceParams)
    quality: QualityParams = Field(default_factory=QualityParams)
    cost_rates: CostRates = Field(default_factory=CostRates)

    @property
    def cycle_time_sec(self) -> float:
        """Seconds per cycle (derived from UPH)."""
        return 3600.0 / self.uph
