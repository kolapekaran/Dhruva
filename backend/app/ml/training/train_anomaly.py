from pathlib import Path
import joblib,numpy as np,json
from sklearn.ensemble import IsolationForest
from app.ml.preprocessing.features import create_features
ART=Path('app/ml/artifacts'); ART.mkdir(parents=True,exist_ok=True)
def main(n=20000):
    rng=np.random.default_rng(42); temp=rng.uniform(-55,5,n); hour=rng.uniform(0,24,n); wind=rng.uniform(0,25,n)
    X=np.array([create_features(t,h,w)[0] for t,h,w in zip(temp,hour,wind)])
    m=IsolationForest(n_estimators=300,contamination=.03,random_state=42,n_jobs=-1); m.fit(X); joblib.dump(m,ART/'anomaly_model.pkl')
    metrics={'model':'IsolationForest','samples':n,'contamination':.03,'synthetic':True,'warning':'Reference anomaly model; field sensor distributions should replace this reference training set.'}
    (ART/'anomaly_model_metrics.json').write_text(json.dumps(metrics,indent=2)); return metrics
if __name__=='__main__': print(main())
