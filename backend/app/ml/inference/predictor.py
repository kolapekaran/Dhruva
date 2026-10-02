"""Production-facing adapter around the supplied AI/ML model artifacts.

This module owns model loading and inference only.

It does not make battery/diesel control decisions. The Digital Twin
and EMS layer remain the source of physical state and control actions.

ML predictions are advisory. Physical plant constraints are enforced
before predictions are exposed to the rest of the system.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from functools import lru_cache

import joblib
import numpy as np

from app.ml.preprocessing.features import create_features
from app.config import STATION_CONFIG


# ---------------------------------------------------------------------
# Model artifact location
# ---------------------------------------------------------------------

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts"


# ---------------------------------------------------------------------
# Forecast result
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class ForecastResult:
    load_kw: float
    solar_kw: float
    wind_kw: float
    renewable_kw: float
    anomaly: int
    failure: int
    failure_probability: float

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------

@lru_cache(maxsize=1)
def _models() -> dict:
    """Load all ML artifacts once and cache them."""

    paths = {
        "load": ARTIFACT_DIR / "load_model.pkl",
        "solar": ARTIFACT_DIR / "solar_model.pkl",
        "wind": ARTIFACT_DIR / "wind_model.pkl",
        "anomaly": ARTIFACT_DIR / "anomaly_model.pkl",
        "failure": ARTIFACT_DIR / "failure_model.pkl",
    }

    missing = [
        str(path)
        for path in paths.values()
        if not path.exists()
    ]

    if missing:
        raise FileNotFoundError(
            "Missing ML artifacts: " + ", ".join(missing)
        )

    loaded = {}
    for name, path in paths.items():
        model = joblib.load(path)
        # Inference is normally tiny (often one row).  Do not fan out
        # RandomForest/IsolationForest prediction across all CPU workers.
        # This avoids unnecessary joblib/scikit-learn parallel overhead and
        # the sklearn.utils.parallel warning on newer scikit-learn versions.
        if hasattr(model, "n_jobs"):
            model.n_jobs = 1
        loaded[name] = model
    return loaded


# ---------------------------------------------------------------------
# Main prediction function
# ---------------------------------------------------------------------

def predict(
    temp_celsius: float,
    hour: float,
    wind_speed_mps: float,
) -> ForecastResult:

    models = _models()

    # -------------------------------------------------------------
    # Feature preparation
    # -------------------------------------------------------------

    X = create_features(
        temp_celsius,
        hour,
        wind_speed_mps,
    )

    # -------------------------------------------------------------
    # ML predictions
    # -------------------------------------------------------------

    load = float(
        models["load"].predict(X)[0]
    )

    solar = float(
        models["solar"].predict(X)[0]
    )

    wind = float(
        models["wind"].predict(X)[0]
    )

    # -------------------------------------------------------------
    # LOAD physical constraints
    # -------------------------------------------------------------

    max_load = (
        STATION_CONFIG.loads.critical_load_kw
        + STATION_CONFIG.loads.important_load_kw
        + STATION_CONFIG.loads.max_flexible_load_kw
        + 2.0
        * STATION_CONFIG.heating.heat_loss_coefficient_kw_per_celsius
        * 60.0
    )

    load = max(
        0.0,
        min(
            load,
            max_load,
        ),
    )

    # -------------------------------------------------------------
    # SOLAR physical constraints
    # -------------------------------------------------------------

    solar = max(
        0.0,
        min(
            solar,
            STATION_CONFIG.solar.installed_capacity_kw,
        ),
    )

    # -------------------------------------------------------------
    # WIND physical constraints
    #
    # The ML model predicts generation.
    # The turbine physics defines whether generation is possible.
    # -------------------------------------------------------------

    wind_config = STATION_CONFIG.wind

    if wind_speed_mps < wind_config.cut_in_wind_speed_mps:

        # Below turbine cut-in speed.
        wind = 0.0

    elif wind_speed_mps >= wind_config.cut_out_wind_speed_mps:
        # At or above cut-out speed, turbine is stopped.
        wind = 0.0

    else:

        # Valid operating region.
        # Never allow ML output above installed capacity.
        wind = max(
            0.0,
            min(
                wind,
                wind_config.installed_capacity_kw,
            ),
        )

    # -------------------------------------------------------------
    # ANOMALY prediction
    # -------------------------------------------------------------

    anomaly = int(
        models["anomaly"].predict(X)[0]
    )

    # -------------------------------------------------------------
    # FAILURE prediction
    # -------------------------------------------------------------

    failure = int(
        models["failure"].predict(X)[0]
    )

    # -------------------------------------------------------------
    # FAILURE probability
    # -------------------------------------------------------------

    if hasattr(
        models["failure"],
        "predict_proba",
    ):

        classes = list(
            models["failure"].classes_
        )

        if 1 in classes:

            failure_probability = float(
                models["failure"]
                .predict_proba(X)[0][
                    classes.index(1)
                ]
            )

        else:

            failure_probability = 0.0

    else:

        failure_probability = float(
            failure == 1
        )

    # -------------------------------------------------------------
    # Final validated forecast
    # -------------------------------------------------------------

    return ForecastResult(
        load_kw=max(
            0.0,
            load,
        ),

        solar_kw=max(
            0.0,
            solar,
        ),

        wind_kw=max(
            0.0,
            wind,
        ),

        renewable_kw=max(
            0.0,
            solar + wind,
        ),

        anomaly=anomaly,

        failure=failure,

        failure_probability=max(
            0.0,
            min(
                1.0,
                failure_probability,
            ),
        ),
    )


# ---------------------------------------------------------------------
# Prediction from Digital Twin state
# ---------------------------------------------------------------------

def predict_from_twin_state(
    state,
) -> ForecastResult:

    ts = state.time.timestamp

    hour = (
        ts.hour
        + ts.minute / 60.0
    )

    return predict(
        state.weather.temperature_celsius,
        hour,
        state.weather.wind_speed_mps,
    )


# ---------------------------------------------------------------------
# Multi-hour forecast
# ---------------------------------------------------------------------

def forecast_horizon(
    temp_celsius: float,
    wind_speed_mps: float,
    start_hour: float,
    hours: int,
) -> list[dict]:

    if hours < 1 or hours > 168:
        raise ValueError(
            "hours must be between 1 and 168"
        )

    results = []

    for offset in range(hours):

        hour = (
            start_hour + offset
        ) % 24

        result = predict(
            temp_celsius,
            hour,
            wind_speed_mps,
        )

        results.append(
            {
                "hour_offset": offset,
                "hour": hour,
                **result.to_dict(),
            }
        )

    return results

def predict_many(inputs: list[tuple[float, float, float]]) -> list[ForecastResult]:
    """Batch inference for forecast horizons.

    Loading each model once and predicting the complete feature matrix at
    once is substantially faster than invoking ``predict`` for every hour.
    Output validation intentionally mirrors ``predict``.
    """
    if not inputs:
        raise ValueError("inputs must not be empty")

    models = _models()
    X = np.vstack([create_features(t, h, w)[0] for t, h, w in inputs])
    loads = np.asarray(models["load"].predict(X), dtype=float)
    solars = np.asarray(models["solar"].predict(X), dtype=float)
    winds = np.asarray(models["wind"].predict(X), dtype=float)
    anomalies = np.asarray(models["anomaly"].predict(X), dtype=int)
    failures = np.asarray(models["failure"].predict(X), dtype=int)

    failure_probabilities = np.asarray(failures == 1, dtype=float)
    if hasattr(models["failure"], "predict_proba"):
        classes = list(models["failure"].classes_)
        if 1 in classes:
            failure_probabilities = np.asarray(models["failure"].predict_proba(X)[:, classes.index(1)], dtype=float)

    max_load = (
        STATION_CONFIG.loads.critical_load_kw
        + STATION_CONFIG.loads.important_load_kw
        + STATION_CONFIG.loads.max_flexible_load_kw
        + 2.0 * STATION_CONFIG.heating.heat_loss_coefficient_kw_per_celsius * 60.0
    )
    wind_config = STATION_CONFIG.wind
    results: list[ForecastResult] = []
    for idx, (_, _, wind_speed) in enumerate(inputs):
        load = float(np.clip(loads[idx], 0.0, max_load))
        solar = float(np.clip(solars[idx], 0.0, STATION_CONFIG.solar.installed_capacity_kw))
        if wind_speed < wind_config.cut_in_wind_speed_mps or wind_speed >= wind_config.cut_out_wind_speed_mps:
            wind = 0.0
        else:
            wind = float(np.clip(winds[idx], 0.0, wind_config.installed_capacity_kw))
        results.append(ForecastResult(
            load_kw=load,
            solar_kw=solar,
            wind_kw=wind,
            renewable_kw=max(0.0, solar + wind),
            anomaly=int(anomalies[idx]),
            failure=int(failures[idx]),
            failure_probability=float(np.clip(failure_probabilities[idx], 0.0, 1.0)),
        ))
    return results


def asset_failure_probabilities(temp_celsius: float, wind_speed_mps: float, irradiance_w_m2: float, load_kw: float, soc_percent: float, fuel_percent: float, battery_health_percent: float, diesel_runtime_hours: float) -> dict:
    models=_models()
    import joblib
    features=np.array([[temp_celsius,wind_speed_mps,irradiance_w_m2,load_kw,soc_percent,fuel_percent,battery_health_percent,diesel_runtime_hours]],dtype=float)
    out={}
    for name in ('battery_failure','generator_failure'):
        path=ARTIFACT_DIR/f'{name}_model.pkl'
        if not path.exists(): out[name]=None; continue
        model = joblib.load(path)
        if hasattr(model, "n_jobs"):
            model.n_jobs = 1
        classes = list(model.classes_)
        out[name] = float(model.predict_proba(features)[0][classes.index(1)]) if 1 in classes else 0.0
    return out
