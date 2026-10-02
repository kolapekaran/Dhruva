"""
Train the Antarctic station solar generation forecasting model.

Features:
    temperature
    hour
    wind speed
    is_night
    wind chill

The generated data models:
    - day/night cycle
    - solar irradiance
    - seasonal variation
    - temperature efficiency
    - wind/snow/ice derating
    - Antarctic low-sun conditions
    - station's 50 kW PV capacity

IMPORTANT:
This uses physically grounded synthetic data.
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
SOLAR_CAPACITY_KW = 50.0

ARTIFACT_DIR = Path("app/ml/artifacts")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = ARTIFACT_DIR / "solar_model.pkl"
METRICS_PATH = ARTIFACT_DIR / "solar_model_metrics.json"


# ---------------------------------------------------------------------
# Solar physics helpers
# ---------------------------------------------------------------------

def solar_irradiance(hour: float, seasonal_factor: float) -> float:
    """
    Approximate normalized solar availability.

    Returns 0 during night and rises toward solar noon.
    Seasonal factor represents Antarctic seasonal variation.
    """

    # Approximate daylight window.
    daylight_start = 3.0
    daylight_end = 21.0

    if hour < daylight_start or hour > daylight_end:
        return 0.0

    # Map daylight to a smooth bell-shaped solar curve.
    daylight_position = (
        (hour - daylight_start)
        / (daylight_end - daylight_start)
    )

    sun_angle = np.pi * daylight_position

    irradiance = np.sin(sun_angle)

    return max(0.0, irradiance * seasonal_factor)


def temperature_efficiency(temp_celsius: float) -> float:
    """
    PV module temperature effect.

    Silicon PV modules generally become less efficient
    as cell temperature increases. Cold conditions therefore
    slightly improve electrical efficiency.

    We use a conservative bounded approximation.
    """

    reference_temperature = 25.0
    coefficient = -0.0035

    factor = 1.0 + coefficient * (
        temp_celsius - reference_temperature
    )

    return float(np.clip(factor, 0.85, 1.15))


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
        wind = rng.uniform(0.0, 25.0)

        features = create_features(
            temperature,
            hour,
            wind,
        )[0]

        # -------------------------------------------------------------
        # Seasonal solar availability
        #
        # This represents long Antarctic seasonal variation.
        # -------------------------------------------------------------

        seasonal_factor = rng.uniform(0.20, 1.0)

        irradiance = solar_irradiance(
            hour,
            seasonal_factor,
        )

        # -------------------------------------------------------------
        # PV temperature efficiency
        # -------------------------------------------------------------

        temp_factor = temperature_efficiency(
            temperature
        )

        # -------------------------------------------------------------
        # Snow / ice / environmental derating
        #
        # Higher wind and extreme cold can be associated with
        # harsh operating conditions. We keep the derating bounded.
        # -------------------------------------------------------------

        icing_probability = 0.05

        if temperature < -25.0:
            icing_probability += 0.10

        if wind > 15.0:
            icing_probability += 0.10

        environmental_derate = rng.uniform(
            1.0 - icing_probability,
            1.0,
        )

        # -------------------------------------------------------------
        # Cloud / atmospheric variation
        # -------------------------------------------------------------

        cloud_factor = rng.uniform(0.65, 1.0)

        # -------------------------------------------------------------
        # Solar output
        # -------------------------------------------------------------

        output = (
            SOLAR_CAPACITY_KW
            * irradiance
            * temp_factor
            * environmental_derate
            * cloud_factor
        )

        # Hard physical limit.
        output = np.clip(
            output,
            0.0,
            SOLAR_CAPACITY_KW,
        )

        # Small measurement/model noise.
        if output > 0:
            output += rng.normal(0.0, 0.4)

        output = np.clip(
            output,
            0.0,
            SOLAR_CAPACITY_KW,
        )

        X.append(features)
        y.append(output)

    return np.asarray(X, dtype=float), np.asarray(y, dtype=float)


# ---------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------

def main():

    print("=" * 70)
    print("ANTARCTIC SOLAR MODEL TRAINING")
    print("=" * 70)

    X, y = generate_dataset()

    print(f"Samples generated : {len(X)}")
    print(f"Features          : {X.shape[1]}")
    print(
        f"Solar output range: "
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

    # MAPE is calculated only where actual solar output > 1 kW
    # because percentage error becomes meaningless near zero.
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
        "target": "solar_generation_kw",
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
        "plant_capacity_kw": SOLAR_CAPACITY_KW,
        "metrics": {
            "MAE_kW": round(float(mae), 4),
            "RMSE_kW": round(float(rmse), 4),
            "R2": round(float(r2), 4),
            "MAPE_percent_daytime": round(float(mape), 4),
        },
        "dataset": {
            "temperature_min_celsius": -55.0,
            "temperature_max_celsius": 5.0,
            "wind_min_mps": 0.0,
            "wind_max_mps": 25.0,
            "synthetic": True,
        },
        "physical_constraints": {
            "minimum_output_kw": 0.0,
            "maximum_output_kw": SOLAR_CAPACITY_KW,
            "night_output_expected_kw": 0.0,
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