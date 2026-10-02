from dataclasses import dataclass
from app.config import LoadsConfig

@dataclass(frozen=True)
class LoadModelInputs:
    critical_load_kw: float
    important_load_kw: float
    flexible_load_kw: float
    heating_load_kw: float

@dataclass(frozen=True)
class LoadModelResult:
    critical_load_kw: float
    important_load_kw: float
    flexible_load_kw: float
    heating_load_kw: float
    requested_load_kw: float
    served_load_kw: float
    shed_load_kw: float
    total_load_kw: float

def calculate_load(inputs: LoadModelInputs, config: LoadsConfig, available_power_kw: float | None = None) -> LoadModelResult:
    vals = [inputs.critical_load_kw, inputs.important_load_kw, inputs.flexible_load_kw, inputs.heating_load_kw]
    if any(v < 0 for v in vals):
        raise ValueError("Loads must be non-negative")
    flexible = min(inputs.flexible_load_kw, config.max_flexible_load_kw)
    requested = inputs.critical_load_kw + inputs.important_load_kw + flexible + inputs.heating_load_kw
    served = requested if available_power_kw is None else max(0.0, min(requested, available_power_kw))
    remaining = served
    critical = min(inputs.critical_load_kw, remaining); remaining -= critical
    important = min(inputs.important_load_kw, remaining); remaining -= important
    flexible_served = min(flexible, remaining); remaining -= flexible_served
    heating_served = min(inputs.heating_load_kw, remaining)
    served_total = critical + important + flexible_served + heating_served
    return LoadModelResult(
        critical, important, flexible_served, heating_served,
        requested, served_total, requested - served_total, served_total
    )
