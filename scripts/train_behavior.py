import fraud  # Set native thread limits before importing numerical libraries.
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from xgboost import XGBClassifier
from fraud.config import load_config
from fraud.schemas import Transaction
from fraud.behavior import History,features,FEATURES,BehaviorLayer
from fraud.evaluation import metrics,save_report

cfg=load_config(); root=Path(cfg['paths']['data']); df=pd.read_csv(root/'transactions.csv').replace({np.nan:None})
history=History(); rows=[]
for item in df.to_dict('records'):
    tx=Transaction.model_validate({k:v for k,v in item.items() if k in Transaction.model_fields})
    rows.append(features(tx,history,cfg)); history.add(tx)
x=pd.DataFrame(rows); x.to_csv(root/'behavior_features.csv',index=False)
train=df.split=='train'; val=df.split=='validation'; test=df.split=='test'; y=df.fraud.astype(int).to_numpy()
scaler=StandardScaler().fit(x.loc[train,FEATURES]); xt=scaler.transform(x.loc[train,FEATURES])
resampled,labels=SMOTE(random_state=cfg['seed']).fit_resample(xt,y[train])
model=XGBClassifier(n_estimators=cfg['behavior']['xgb_estimators'],max_depth=cfg['behavior']['xgb_max_depth'],learning_rate=cfg['behavior']['xgb_learning_rate'],
                    eval_metric='logloss',random_state=cfg['seed'],n_jobs=4)
model.fit(resampled,labels)
iso=IsolationForest(n_estimators=cfg['behavior']['isolation_estimators'],random_state=cfg['seed'],n_jobs=4).fit(xt[y[train]==0])
raw=-iso.score_samples(xt[y[train]==0]); lo,hi=np.quantile(raw,cfg['behavior']['isolation_quantiles'])
bundle=dict(scaler=scaler,xgb=model,isolation=iso,q_low=lo,q_high=hi,features=FEATURES,
            background=x.loc[train,FEATURES].sample(16,random_state=cfg['seed']).to_numpy())
joblib.dump(bundle,Path(cfg['paths']['models'])/'behavior.joblib')
layer=BehaviorLayer(cfg)
report={'positive_definition':'Any fraudulent transaction, including social-only fraud with normal behavior.',
        'smote':'Training partition only, after training-only scaling. Indicator columns may be interpolated; synthetic demo.',
        'split':'chronological 60/20/20; history features built strictly before each event',
        'train_count':int(train.sum()),'resampled_train_count':len(labels),'validation':metrics(y[val],layer.predict_array(x.loc[val,FEATURES])),
        'test':metrics(y[test],layer.predict_array(x.loc[test,FEATURES])),
        'xgboost_test':metrics(y[test],model.predict_proba(scaler.transform(x.loc[test,FEATURES]))[:,1]),
        'isolation_test':metrics(y[test],np.clip((-iso.score_samples(scaler.transform(x.loc[test,FEATURES]))-lo)/(hi-lo),0,1))}
save_report(cfg,'behavior',report)
