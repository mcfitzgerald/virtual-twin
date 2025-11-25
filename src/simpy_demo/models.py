import uuid
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from enum import Enum


class MaterialType(str, Enum):
    TUBE = "Tube"
    CASE = "Case"
    PALLET = "Pallet"
    NONE = "None"


class Product(BaseModel):
    uid: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: MaterialType
    created_at: float
    parent_machine: str
    is_defective: bool = False
    genealogy: List[str] = Field(default_factory=list)  # IDs of children components
    telemetry: Dict[str, Any] = Field(default_factory=dict)  # Sensor data (temp, weight)


class MachineConfig(BaseModel):
    name: str
    uph: int = Field(..., description="Target Speed (Units Per Hour)")
    batch_in: int = Field(1, description="Items required to start cycle")
    output_type: MaterialType = MaterialType.NONE

    # Reliability (Major Breakdowns - Availability Loss)
    mtbf_min: Optional[float] = None  # Mean Time Between Failures (Time-based)
    mttr_min: float = 60.0  # Mean Time To Repair (Default: 1 hour)

    # Microstops (Jams - Performance Loss)
    jam_prob: float = 0.0  # Probability (0-1) of a jam per cycle
    jam_time_sec: float = 10.0  # Time to clear a jam (Default: 10 sec)

    # Quality (Yield Loss)
    defect_rate: float = 0.0  # Prob of creating a defect
    detection_prob: float = 0.0  # Prob of detecting a defect (Inspection)

    # Constraints
    buffer_capacity: int = 50  # Input buffer size

    @property
    def cycle_time_sec(self) -> float:
        return 3600.0 / self.uph


class ScenarioConfig(BaseModel):
    name: str
    duration_hours: float = 8.0
    random_seed: Optional[int] = 42
    layout: List[MachineConfig]
