"""Production line topology definitions (structure only, no parameters)."""

from simpy_demo.models import MaterialType


class Station:
    """Defines a station in the production line (structure only, no params)."""

    def __init__(
        self,
        name: str,
        batch_in: int = 1,
        output_type: MaterialType = MaterialType.NONE,
    ):
        self.name = name
        self.batch_in = batch_in
        self.output_type = output_type


class CosmeticsLine:
    """Cosmetics production line topology.

    Line structure: [Source] -> Filler -> Inspector -> Packer -> Palletizer -> [Sink]

    Note: Depalletizer removed - infinite source handled by engine.
    """

    stations = [
        Station("Filler", batch_in=1, output_type=MaterialType.TUBE),
        Station("Inspector", batch_in=1, output_type=MaterialType.NONE),
        Station("Packer", batch_in=12, output_type=MaterialType.CASE),
        Station("Palletizer", batch_in=60, output_type=MaterialType.PALLET),
    ]
