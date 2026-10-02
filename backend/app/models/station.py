from dataclasses import dataclass

@dataclass(frozen=True)
class StationMetadata:
    station_id: str = "MAITRI-ANT-001"
    name: str = "Maitri Research Station"
    environment: str = "Antarctic reference environment"
    data_classification: str = "synthetic_reference"
