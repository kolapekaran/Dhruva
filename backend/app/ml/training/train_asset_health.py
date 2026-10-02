from __future__ import annotations
from pathlib import Path
import json, joblib, numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score
ART=Path('app/ml/artifacts'); ART.mkdir(parents=True,exist_ok=True)
SEED=42
FEATURES=['temperature_celsius','wind_speed_mps','irradiance_w_m2','load_kw','soc_percent','fuel_percent','battery_health_percent','diesel_runtime_hours']
def train(kind:str,n:int=30000):
 rng=np.random.default_rng(SEED+(0 if kind=='battery' else 1))
 temp=rng.uniform(-65,8,n); wind=rng.uniform(0,35,n); irr=rng.uniform(0,900,n); load=rng.uniform(20,130,n); soc=rng.uniform(10,100,n); fuel=rng.uniform(0,100,n); batt=rng.uniform(55,100,n); run=rng.uniform(0,4000,n)
 if kind=='battery':
  score=(0.050*np.maximum(0,-temp-10)+0.80*np.maximum(0,20-soc)/20+0.55*np.maximum(0,soc-95)/5+0.055*np.maximum(0,75-batt)+0.018*wind+0.006*np.maximum(0,load-100))
 else:
  score=(0.030*np.maximum(0,-temp-15)+0.65*np.maximum(0,10-fuel)/10+0.00045*run+0.025*wind+0.55*np.maximum(0,load-110)/20)
 threshold=float(np.quantile(score,0.70))
 y=(score>=threshold).astype(int)
 # Measurement uncertainty: flip a small fraction only, while keeping a learnable physical boundary.
 flip=rng.random(n)<0.025
 y[flip]=1-y[flip]
 X=np.column_stack([temp,wind,irr,load,soc,fuel,batt,run])
 xt,xv,yt,yv=train_test_split(X,y,test_size=.2,random_state=SEED,stratify=y)
 m=RandomForestClassifier(n_estimators=300,max_depth=16,min_samples_leaf=3,class_weight='balanced',random_state=SEED,n_jobs=-1)
 m.fit(xt,yt); p=m.predict_proba(xv)[:,1]
 path=ART/f'{kind}_failure_model.pkl'; joblib.dump(m,path)
 metrics={'model':'RandomForestClassifier','target':kind+'_failure','samples':n,'positive_rate':float(y.mean()),'features':FEATURES,'accuracy':float(accuracy_score(yv,(p>=.5).astype(int))),'roc_auc':float(roc_auc_score(yv,p)),'synthetic':True,'warning':'Reference stress model; not field-calibrated.'}
 (ART/f'{kind}_failure_model_metrics.json').write_text(json.dumps(metrics,indent=2)); print(metrics)
if __name__=='__main__': train('battery'); train('generator')
