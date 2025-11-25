"""Baseline equipment parameters for the cosmetics line."""

from simpy_demo.config import EquipmentParams
from simpy_demo.models import ReliabilityParams, PerformanceParams, QualityParams


BASELINE: dict[str, EquipmentParams] = {
    "Filler": EquipmentParams(
        uph=10000,
        buffer_capacity=50,
        reliability=ReliabilityParams(mtbf_min=120, mttr_min=15),
        performance=PerformanceParams(jam_prob=0.01, jam_time_sec=15),
        quality=QualityParams(defect_rate=0.02),
    ),
    "Inspector": EquipmentParams(
        uph=11000,
        buffer_capacity=20,
        quality=QualityParams(detection_prob=0.95),
    ),
    "Packer": EquipmentParams(
        uph=12000,
        buffer_capacity=100,
        reliability=ReliabilityParams(mtbf_min=240),
        performance=PerformanceParams(jam_prob=0.05, jam_time_sec=30),
    ),
    "Palletizer": EquipmentParams(
        uph=13000,
        buffer_capacity=40,
        reliability=ReliabilityParams(mtbf_min=480),
    ),
}
