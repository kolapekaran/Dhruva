from __future__ import annotations
from pathlib import Path
import json, joblib, numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score
from app.ml.preprocessing.features import create_features

ART=Path('app/ml/artifacts'); ART.mkdir(parents=True,exist_ok=True); SEED=42

def main(n=30000):
    rng=np.random.default_rng(SEED)
    t=rng.uniform(-60,10,n); h=rng.uniform(0,24,n); w=rng.uniform(0,30,n)
    X=np.array([create_features(a,b,c)[0] for a,b,c in zip(t,h,w)])
    stress=.025*np.maximum(0,-t-25)+.025*w+.30*(h<3)+.30*(h>21)
    threshold=float(np.quantile(stress,.70)); y=(stress>=threshold).astype(int)
    flip=rng.random(n)<.025; y[flip]=1-y[flip]
    a,b,c,d=train_test_split(X,y,test_size=.2,random_state=SEED,stratify=y)
    m=RandomForestClassifier(n_estimators=300,max_depth=16,min_samples_leaf=3,class_weight='balanced',random_state=SEED,n_jobs=-1)
    m.fit(a,c); pr=m.predict_proba(b)[:,1]
    joblib.dump(m,ART/'failure_model.pkl')
    metrics={'model':'RandomForestClassifier','target':'general_asset_failure','samples':n,'positive_rate':float(y.mean()),'accuracy':float(accuracy_score(d,pr>=.5)),'roc_auc':float(roc_auc_score(d,pr)),'synthetic':True,'warning':'Reference stress model; not field-calibrated.'}
    (ART/'failure_model_metrics.json').write_text(json.dumps(metrics,indent=2)); return metrics

if __name__=='__main__': print(main())
