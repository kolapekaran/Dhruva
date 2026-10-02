"""
Train the Antarctic station wind generation forecasting model.

Reference turbine:
    Rated capacity : 100 kW
    Cut-in speed   : 3 m/s
    Rated speed    : 12 m/s
    Cut-out speed  : 25 m/s

Features:
    temperature
    hour
    wind speed
    is_night
    wind chill

IMPORTANT:
This is physically grounded synthetic training data.
It is not measured Antarctic telemetry.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

from app.ml.preprocessing.features import create_features


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

RANDOM_SEED = 42
N_SAMPLES = 10000

RATED_POWER_KW = 100.0
CUT_IN_MPS = 3.0
RATED_MPS = 12.0
CUT_OUT_MPS = 25.0

ARTIFACT_DIR = Path("app/ml/artifacts")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = ARTIFACT_DIR / "wind_model.pkl"
METRICS_PATH = ARTIFACT_DIR / "wind_model_metrics.json"


# ---------------------------------------------------------------------
# Physical wind turbine model
# ---------------------------------------------------------------------

def turbine_power_curve(wind_speed_mps: float) -> float:
    """
    Approximate wind turbine power curve.

    Below cut-in:
        0 kW

    Between cut-in and rated:
        cubic increase

    Between rated and cut-out:
        rated power

    Above cut-out:
        0 kW
    """

    if wind_speed_mps < CUT_IN_MPS:
        return 0.0

    if wind_speed_mps >= CUT_OUT_MPS:
        return 0.0

    if wind_speed_mps >= RATED_MPS:
        return RATED_POWER_KW

    normalized = (
        (wind_speed_mps - CUT_IN_MPS)
        / (RATED_MPS - CUT_IN_MPS)
    )

    return RATED_POWER_KW * normalized ** 3


def generate_dataset(
    n_samples: int = N_SAMPLES,
    seed: int = RANDOM_SEED,
):
    rng = np.random.default_rng(seed)

    X = []
    y = []

    for _ in range(n_samples):

        # -------------------------------------------------------------
        # Antarctic environmental conditions
        # -------------------------------------------------------------

        temperature = rng.uniform(-55.0, 5.0)
        hour = rng.uniform(0.0, 24.0)
        wind = rng.uniform(0.0, 30.0)

        features = create_features(
            temperature,
            hour,
            wind,
        )[0]

        # -------------------------------------------------------------
        # Base turbine power curve
        # -------------------------------------------------------------

        power = turbine_power_curve(wind)

        # -------------------------------------------------------------
        # Cold-weather / icing derating
        #
        # We model icing as a bounded random availability factor.
        # It is stronger under very cold and high-wind conditions.
        # -------------------------------------------------------------

        derate = 1.0

        if temperature < -25.0:
            derate -= rng.uniform(0.0, 0.10)

        if temperature < -40.0:
            derate -= rng.uniform(0.0, 0.10)

        if wind > 15.0 and temperature < -10.0:
            derate -= rng.uniform(0.0, 0.10)

        derate = float(np.clip(derate, 0.70, 1.0))

        power *= derate

        # -------------------------------------------------------------
        # Small operational variability
        # -------------------------------------------------------------

        if power > 0:
            power += rng.normal(0.0, 1.0)

        # -------------------------------------------------------------
        # Hard physical limits
        # -------------------------------------------------------------

        power = float(
            np.clip(
                power,
                0.0,
                RATED_POWER_KW,
            )
        )

        X.append(features)
        y.append(power)

    return np.asarray(X, dtype=float), np.asarray(y, dtype=float)


# ---------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------

def main():

    print("=" * 70)
    print("ANTARCTIC WIND MODEL TRAINING")
    print("=" * 70)

    X, y = generate_dataset()

    print(f"Samples generated : {len(X)}")
    print(f"Features          : {X.shape[1]}")
    print(
        f"Wind output range : "
        f"{y.min():.2f} - {y.max():.2f} kW"
    )
    print(f"Mean output       : {y.mean():.2f} kW")

    # -------------------------------------------------------------
    # Train/test split
    # -------------------------------------------------------------

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=RANDOM_SEED,
    )

    # -------------------------------------------------------------
    # Random Forest
    # -------------------------------------------------------------

    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=20,
        min_samples_leaf=3,
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )

    model.fit(
        X_train,
        y_train,
    )

    # -------------------------------------------------------------
    # Evaluation
    # -------------------------------------------------------------

    predictions = model.predict(X_test)

    mae = mean_absolute_error(
        y_test,
        predictions,
    )

    rmse = np.sqrt(
        mean_squared_error(
            y_test,
            predictions,
        )
    )

    r2 = r2_score(
        y_test,
        predictions,
    )

    valid = y_test > 1.0

    if np.any(valid):
        mape = np.mean(
            np.abs(
                (y_test[valid] - predictions[valid])
                / y_test[valid]
            )
        ) * 100.0
    else:
        mape = 0.0

    # -------------------------------------------------------------
    # Save model
    # -------------------------------------------------------------

    joblib.dump(
        model,
        MODEL_PATH,
    )

    metrics = {
        "model": "RandomForestRegressor",
        "target": "wind_generation_kw",
        "samples": int(len(X)),
        "training_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "features": [
            "temperature_celsius",
            "hour",
            "wind_speed_mps",
            "is_night",
            "wind_chill",
        ],
        "turbine": {
            "rated_power_kw": RATED_POWER_KW,
            "cut_in_mps": CUT_IN_MPS,
            "rated_speed_mps": RATED_MPS,
            "cut_out_mps": CUT_OUT_MPS,
        },
        "metrics": {
            "MAE_kW": round(float(mae), 4),
            "RMSE_kW": round(float(rmse), 4),
            "R2": round(float(r2), 4),
            "MAPE_percent_operating": round(float(mape), 4),
        },
        "dataset": {
            "temperature_min_celsius": -55.0,
            "temperature_max_celsius": 5.0,
            "wind_min_mps": 0.0,
            "wind_max_mps": 30.0,
            "synthetic": True,
        },
        "physical_constraints": {
            "minimum_output_kw": 0.0,
            "maximum_output_kw": RATED_POWER_KW,
        },
        "warning": (
            "Training data is physically grounded synthetic data. "
            "It must not be presented as measured Antarctic telemetry."
        ),
    }

    METRICS_PATH.write_text(
        json.dumps(
            metrics,
            indent=2,
        ),
        encoding="utf-8",
    )

    # -------------------------------------------------------------
    # Report
    # -------------------------------------------------------------

    print()
    print("MODEL EVALUATION")
    print("-" * 70)
    print(f"MAE   : {mae:.3f} kW")
    print(f"RMSE  : {rmse:.3f} kW")
    print(f"R²    : {r2:.4f}")
    print(f"MAPE  : {mape:.2f}%")

    print()
    print("MODEL SAVED")
    print("-" * 70)
    print(f"Model   : {MODEL_PATH}")
    print(f"Metrics : {METRICS_PATH}")

    print()
    print("IMPORTANT:")
    print(
        "These metrics measure performance on synthetic "
        "data, not real Antarctic telemetry."
    )

    print("=" * 70)


if __name__ == "__main__":
    main()