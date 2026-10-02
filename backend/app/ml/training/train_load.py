"""
Train the Antarctic station load forecasting model.

The model predicts total station electrical load from:
    temperature, hour, wind speed, is_night, wind chill

The synthetic training data is designed around the reference
Antarctic station and its heating-dominated load profile.

IMPORTANT:
This is a physically grounded synthetic dataset, not measured
Antarctic telemetry. Real station telemetry should replace it
when available.
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
N_SAMPLES = 5000

ARTIFACT_DIR = Path("app/ml/artifacts")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = ARTIFACT_DIR / "load_model.pkl"
METRICS_PATH = ARTIFACT_DIR / "load_model_metrics.json"


# ---------------------------------------------------------------------
# Synthetic Antarctic load generation
# ---------------------------------------------------------------------

def generate_dataset(
    n_samples: int = N_SAMPLES,
    seed: int = RANDOM_SEED,
):
    rng = np.random.default_rng(seed)

    X = []
    y = []

    for _ in range(n_samples):
        # Antarctic operating conditions.
        temperature = rng.uniform(-55.0, 5.0)
        hour = rng.uniform(0.0, 24.0)
        wind = rng.uniform(0.0, 25.0)

        features = create_features(
            temperature,
            hour,
            wind,
        )[0]

        # -------------------------------------------------------------
        # Base station electrical demand
        # -------------------------------------------------------------

        base_load = 30.0

        # -------------------------------------------------------------
        # Daily activity pattern
        #
        # Research/office activity is generally higher during the day.
        # -------------------------------------------------------------

        daily_activity = (
            5.0
            + 5.0 * np.exp(-((hour - 10.0) / 4.0) ** 2)
            + 4.0 * np.exp(-((hour - 18.0) / 3.0) ** 2)
        )

        # -------------------------------------------------------------
        # Heating demand
        #
        # Heating requirement increases as outdoor temperature falls.
        # Reference indoor target ≈ 20°C.
        # -------------------------------------------------------------

        heating_load = max(0.0, (20.0 - temperature) * 0.80)

        # -------------------------------------------------------------
        # Wind/infiltration effect
        #
        # Stronger winds can increase building heat loss.
        # Keep this effect modest compared with temperature.
        # -------------------------------------------------------------

        wind_effect = 0.15 * wind

        # -------------------------------------------------------------
        # Night reduction
        #
        # Some non-critical activity decreases during night.
        # Heating remains active.
        # -------------------------------------------------------------

        is_night = hour < 6.0 or hour > 20.0

        if is_night:
            activity_factor = 0.65
        else:
            activity_factor = 1.0

        activity_load = daily_activity * activity_factor

        # -------------------------------------------------------------
        # Total electrical load
        # -------------------------------------------------------------

        load = (
            base_load
            + activity_load
            + heating_load
            + wind_effect
        )

        # Small measurement/modeling noise.
        noise = rng.normal(0.0, 1.5)

        load = max(20.0, load + noise)

        X.append(features)
        y.append(load)

    return np.asarray(X, dtype=float), np.asarray(y, dtype=float)


# ---------------------------------------------------------------------
# Train and evaluate
# ---------------------------------------------------------------------

def main():
    print("=" * 70)
    print("ANTARCTIC LOAD MODEL TRAINING")
    print("=" * 70)

    X, y = generate_dataset()

    print(f"Samples generated : {len(X)}")
    print(f"Features          : {X.shape[1]}")
    print(f"Load range        : {y.min():.2f} - {y.max():.2f} kW")
    print(f"Mean load         : {y.mean():.2f} kW")

    # Keep a completely unseen test set.
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=RANDOM_SEED,
    )

    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=18,
        min_samples_leaf=3,
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    mae = mean_absolute_error(y_test, predictions)
    rmse = np.sqrt(mean_squared_error(y_test, predictions))
    r2 = r2_score(y_test, predictions)

    # Mean absolute percentage error.
    mape = np.mean(
        np.abs((y_test - predictions) / np.maximum(np.abs(y_test), 1e-6))
    ) * 100.0

    # -----------------------------------------------------------------
    # Save model
    # -----------------------------------------------------------------

    joblib.dump(model, MODEL_PATH)

    # Save evaluation information beside the model.
    metrics = {
        "model": "RandomForestRegressor",
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
        "metrics": {
            "MAE_kW": round(float(mae), 4),
            "RMSE_kW": round(float(rmse), 4),
            "R2": round(float(r2), 4),
            "MAPE_percent": round(float(mape), 4),
        },
        "dataset": {
            "temperature_min_celsius": -55.0,
            "temperature_max_celsius": 5.0,
            "wind_min_mps": 0.0,
            "wind_max_mps": 25.0,
            "synthetic": True,
        },
        "warning": (
            "Training data is physically grounded synthetic data. "
            "It must not be presented as measured Antarctic telemetry."
        ),
    }

    METRICS_PATH.write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8",
    )

    # -----------------------------------------------------------------
    # Report
    # -----------------------------------------------------------------

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
        "These metrics measure performance on synthetic generated data, "
        "not real Antarctic station telemetry."
    )

    print("=" * 70)


if __name__ == "__main__":
    main()