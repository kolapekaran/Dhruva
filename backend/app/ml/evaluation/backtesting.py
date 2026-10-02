"""Real-data-ready historical backtesting for DHRUVA.

The pipeline accepts timestamped observations, validates provenance/quality,
executes the existing production ML adapters without mutating the Digital Twin,
and evaluates predictions on chronological holdout windows.  It is deliberately
agnostic about whether the records are synthetic, reference, or field telemetry.
The caller must provide provenance; the engine never upgrades reference data to
field validation.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
import csv
import io
import json
import math
import hashlib

from app.ml.evaluation.forecast_metrics import evaluate_forecast
from app.ml.evaluation.calibration import split_conformal_evaluation
from app.ml.inference.predictor import predict, ARTIFACT_DIR

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "historical"
DATA_FILE = DATA_DIR / "observations.jsonl"

ALLOWED_PROVENANCE = {"FIELD_TELEMETRY", "REFERENCE", "SYNTHETIC", "SIMULATION"}
REQUIRED_COLUMNS = ("timestamp", "temperature_celsius", "wind_speed_mps")
TARGET_COLUMNS = ("load_kw", "solar_kw", "wind_kw")


@dataclass(frozen=True)
class Observation:
    timestamp: str
    temperature_celsius: float
    wind_speed_mps: float
    solar_irradiance_w_m2: float = 0.0
    snowfall_rate: float = 0.0
    load_kw: float | None = None
    solar_kw: float | None = None
    wind_kw: float | None = None
    provenance: str = "REFERENCE"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _number(value: Any, name: str, low: float, high: float) -> float:
    x = float(value)
    if not math.isfinite(x) or x < low or x > high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return x


def parse_observation(raw: dict[str, Any]) -> Observation:
    missing = [k for k in REQUIRED_COLUMNS if raw.get(k) in (None, "")]
    if missing:
        raise ValueError("missing required columns: " + ", ".join(missing))
    ts = datetime.fromisoformat(str(raw["timestamp"]).replace("Z", "+00:00"))
    provenance = str(raw.get("provenance", "REFERENCE")).upper()
    if provenance not in ALLOWED_PROVENANCE:
        raise ValueError(f"unsupported provenance: {provenance}")
    def optional(name: str, low: float, high: float):
        value = raw.get(name)
        return None if value in (None, "") else _number(value, name, low, high)
    return Observation(
        timestamp=ts.isoformat(),
        temperature_celsius=_number(raw["temperature_celsius"], "temperature_celsius", -90, 20),
        wind_speed_mps=_number(raw["wind_speed_mps"], "wind_speed_mps", 0, 80),
        solar_irradiance_w_m2=_number(raw.get("solar_irradiance_w_m2", 0), "solar_irradiance_w_m2", 0, 2000),
        snowfall_rate=_number(raw.get("snowfall_rate", 0), "snowfall_rate", 0, 100),
        load_kw=optional("load_kw", 0, 500),
        solar_kw=optional("solar_kw", 0, 500),
        wind_kw=optional("wind_kw", 0, 500),
        provenance=provenance,
    )


def validate_dataset(records: Iterable[Observation]) -> dict[str, Any]:
    rows = list(records)
    timestamps = [datetime.fromisoformat(r.timestamp) for r in rows]
    duplicate_count = len(timestamps) - len(set(timestamps))
    ordered = timestamps == sorted(timestamps)
    target_counts = {k: sum(getattr(r, k) is not None for r in rows) for k in TARGET_COLUMNS}
    required_count = len(rows) * len(REQUIRED_COLUMNS)
    return {
        "sample_count": len(rows),
        "duplicate_timestamps": duplicate_count,
        "chronological": ordered,
        "target_observations": target_counts,
        "target_completeness_percent": {
            k: round(100 * v / len(rows), 3) if rows else 0.0 for k, v in target_counts.items()
        },
        "required_field_completeness_percent": 100.0 if rows and required_count else 0.0,
        "provenance_counts": {p: sum(r.provenance == p for r in rows) for p in sorted(ALLOWED_PROVENANCE)},
        "quality_status": "PASS" if rows and duplicate_count == 0 and ordered else "DEGRADED",
    }


def _split(rows: list[Observation], calibration_fraction: float) -> tuple[list[Observation], list[Observation]]:
    if len(rows) < 4:
        raise ValueError("at least 4 observations are required for chronological backtesting")
    if not 0.2 <= calibration_fraction <= 0.8:
        raise ValueError("calibration_fraction must be between 0.2 and 0.8")
    cut = max(2, min(len(rows) - 2, int(len(rows) * calibration_fraction)))
    return rows[:cut], rows[cut:]


def run_backtest(records: list[Observation], calibration_fraction: float = 0.6) -> dict[str, Any]:
    # Preserve caller order: historical evaluation must be chronological, and silently
    # sorting an invalid input would hide a data-integrity problem.
    rows = list(records)
    quality = validate_dataset(rows)
    if quality["duplicate_timestamps"]:
        raise ValueError("duplicate timestamps must be removed before backtesting")
    if not quality["chronological"]:
        raise ValueError("timestamps must be chronological for backtesting")

    predictions = {k: [] for k in TARGET_COLUMNS}
    actuals = {k: [] for k in TARGET_COLUMNS}
    evaluated_rows = 0
    for row in rows:
        result = predict(
            row.temperature_celsius,
            datetime.fromisoformat(row.timestamp).hour + datetime.fromisoformat(row.timestamp).minute / 60.0,
            row.wind_speed_mps,
        )
        for key, pred_key in (("load_kw", "load_kw"), ("solar_kw", "solar_kw"), ("wind_kw", "wind_kw")):
            actual = getattr(row, key)
            if actual is not None:
                actuals[key].append(float(actual))
                predictions[key].append(float(getattr(result, pred_key)))
        evaluated_rows += 1

    metrics = {}
    calibration = {}
    for key in TARGET_COLUMNS:
        if not actuals[key]:
            metrics[key] = {"status": "NO_TARGET_DATA"}
            continue
        metrics[key] = {"status": "EVALUATED", **evaluate_forecast(actuals[key], predictions[key])}
        cal_pairs = [(float(getattr(r, key)), float(predictions[key][i])) for i, r in enumerate([r for r in rows if getattr(r, key) is not None])]
        # Preserve chronological order of target-bearing rows for the split.
        split_idx = max(2, min(len(cal_pairs) - 2, int(len(cal_pairs) * calibration_fraction)))
        c_actual = [x[0] for x in cal_pairs[:split_idx]]
        c_pred = [x[1] for x in cal_pairs[:split_idx]]
        e_actual = [x[0] for x in cal_pairs[split_idx:]]
        e_pred = [x[1] for x in cal_pairs[split_idx:]]
        if len(c_actual) >= 2 and len(e_actual) >= 2:
            calibration[key] = split_conformal_evaluation(c_actual, c_pred, e_actual, e_pred, alpha=0.10)
        else:
            calibration[key] = {"status": "INSUFFICIENT_TARGET_DATA"}

    provenance = "FIELD_TELEMETRY" if rows and all(r.provenance == "FIELD_TELEMETRY" for r in rows) else "NON_FIELD_OR_MIXED"
    return {
        "engine": "DHRUVA_HISTORICAL_BACKTEST_V1",
        "dataset": quality,
        "evaluation": {
            "rows_processed": evaluated_rows,
            "metrics": metrics,
            "calibration": calibration,
            "chronological_holdout": True,
            "calibration_fraction": calibration_fraction,
        },
        "provenance": provenance,
        "field_validated": provenance == "FIELD_TELEMETRY",
        "station_state_mutated": False,
        "note": "Metrics are only representative of the supplied dataset. Field validation requires independently verified Maitri telemetry and an agreed validation protocol.",
    }


def parse_csv_text(text: str) -> list[Observation]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV header is required")
    missing = [k for k in REQUIRED_COLUMNS if k not in reader.fieldnames]
    if missing:
        raise ValueError("missing required CSV columns: " + ", ".join(missing))
    rows = [parse_observation(dict(r)) for r in reader]
    if not rows:
        raise ValueError("CSV contains no observations")
    return rows


def append_observations(records: list[Observation]) -> dict[str, Any]:
    quality = validate_dataset(records)
    if quality["duplicate_timestamps"]:
        raise ValueError("duplicate timestamps are not allowed")
    if not quality["chronological"]:
        raise ValueError("timestamps must be chronological for persistence")
    existing = load_stored_observations(limit=5000)
    if existing and datetime.fromisoformat(records[0].timestamp) <= datetime.fromisoformat(existing[-1].timestamp):
        raise ValueError("new observations must be later than the latest stored timestamp")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open("a", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row.to_dict(), separators=(",", ":")) + "\n")
    return {"stored_count": len(records), "path": str(DATA_FILE), "storage": "local_jsonl_prototype"}


def load_stored_observations(limit: int = 5000) -> list[Observation]:
    if not DATA_FILE.exists():
        return []
    lines = DATA_FILE.read_text(encoding="utf-8").splitlines()[-limit:]
    return [parse_observation(json.loads(line)) for line in lines if line.strip()]


def artifact_manifest() -> dict[str, Any]:
    """Return deterministic hashes for ML artifacts used by the runtime.

    This is provenance evidence only; a hash does not imply that an artifact was
    trained on field telemetry or independently validated.
    """
    artifacts = {}
    if ARTIFACT_DIR.exists():
        for path in sorted(ARTIFACT_DIR.glob("*.pkl")):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            artifacts[path.name] = {"sha256": digest, "bytes": path.stat().st_size}
    return {
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "provenance": "artifact_integrity_only",
    }
