import fraud  # Set native thread limits before importing numerical libraries.
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
from fraud.config import load_config
from fraud.schemas import Transaction
from fraud.behavior import History,FEATURES as BF
from fraud.network import features,NetworkLayer,FEATURES as NF
from fraud.text import rule_signals
from fraud.evaluation import metrics,save_report

cfg=load_config(); root=Path(cfg['paths']['data']); df=pd.read_csv(root/'transactions.csv').replace({np.nan:None})
history=History(); layer=NetworkLayer(cfg); rows=[]; scores=[]
for item in df.to_dict('records'):
    tx=Transaction.model_validate({k:v for k,v in item.items() if k in Transaction.model_fields})
    f=features(tx,history,cfg); rows.append(f); scores.append(layer.score(f)['score'])
    hits,_=rule_signals(tx.text or '',cfg)
    # Use only past observable rule flags; NEVER prior ground-truth fraud labels.
    history.add(tx,float(any(h['score']>=cfg['nlp']['rule_short_circuit'] for h in hits)))
nf=pd.DataFrame(rows); nf.to_csv(root/'network_features.csv',index=False)
bf=pd.read_csv(root/'behavior_features.csv'); x=pd.concat([bf,nf],axis=1)
train=df.split=='train'; val=df.split=='validation'; test=df.split=='test'; y=df.fraud.astype(int).to_numpy()
scaler=StandardScaler().fit(x.loc[train]); xt=scaler.transform(x.loc[train]); xs,ys=SMOTE(random_state=cfg['seed']).fit_resample(xt,y[train])
model=XGBClassifier(n_estimators=cfg['behavior']['xgb_estimators'],max_depth=cfg['behavior']['xgb_max_depth'],learning_rate=cfg['behavior']['xgb_learning_rate'],
                    eval_metric='logloss',random_state=cfg['seed'],n_jobs=4).fit(xs,ys)
joblib.dump(dict(scaler=scaler,xgb=model,features=BF+NF),Path(cfg['paths']['models'])/'network_ablation.joblib')
base=joblib.load(Path(cfg['paths']['models'])/'behavior.joblib')
before=metrics(y[test],base['xgb'].predict_proba(base['scaler'].transform(bf.loc[test,BF]))[:,1])
after=metrics(y[test],model.predict_proba(scaler.transform(x.loc[test]))[:,1])
save_report(cfg,'network',{'positive_definition':'Any fraudulent transaction; network-only scores cannot detect all social-only scams.',
    'network_validation':metrics(y[val],np.array(scores)[val]),'network_test':metrics(y[test],np.array(scores)[test]),
    'ablation_before_behavior_xgb':before,'ablation_after_behavior_plus_graph_xgb':after,
    'delta_f1':after['f1']-before['f1'],'delta_roc_auc':after['roc_auc']-before['roc_auc'],
    'ablation_scope':'Same chronological split, XGBoost hyperparameters and train-only SMOTE. Diagnostic model, not used in weighted fusion.'})
