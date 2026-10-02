from fastapi import APIRouter
from pathlib import Path
import sklearn
from app.ml.inference.predictor import ARTIFACT_DIR
router=APIRouter(tags=['Health'])
@router.get('/health/detailed')
def detailed_health():
    required=['load_model.pkl','solar_model.pkl','wind_model.pkl','anomaly_model.pkl','failure_model.pkl','battery_failure_model.pkl','generator_failure_model.pkl']
    present={n:(ARTIFACT_DIR/n).exists() for n in required}
    return {'status':'ok' if all(present.values()) else 'degraded','service':'dhruva','ml_artifacts':present,'ml_artifacts_directory':str(Path(ARTIFACT_DIR).name),'ml_runtime':{'scikit_learn':sklearn.__version__},'data_mode':'synthetic_reference_with_telemetry_ingestion','note':'Reference forecasts use physically grounded synthetic weather until real station telemetry is connected. Health probabilities are advisory and require field calibration for deployment.'}
