import fraud  # Set native thread limits before importing numerical libraries.
from pathlib import Path
import numpy as np
import pandas as pd
from fraud.config import load_config
from fraud.text import TextLayer
from fraud.behavior import BehaviorLayer,FEATURES as BF
from fraud.network import NetworkLayer
from fraud.fusion import fuse
from fraud.evaluation import metrics,save_report

cfg=load_config(); root=Path(cfg['paths']['data']); df=pd.read_csv(root/'transactions.csv').replace({np.nan:None})
bf=pd.read_csv(root/'behavior_features.csv'); nf=pd.read_csv(root/'network_features.csv')
text=TextLayer(cfg); behavior=BehaviorLayer(cfg); network=NetworkLayer(cfg)
# Exact repeated strings are memoized only in this offline evaluator, not in latency measurements.
cache={}; output=[]
bs=behavior.predict_array(bf[BF])
for i,item in enumerate(df.to_dict('records')):
    if item['split']=='train': continue
    t=item['text']
    if t not in cache: cache[t]=text.score(t)
    ts=cache[t]; ns=network.score(nf.iloc[i].to_dict())
    sub=dict(text=ts['score'],behavioral=float(bs[i]),network=ns['score'],rules=ts['rules'])
    result=fuse(sub,cfg)
    output.append(dict(transaction_id=item['transaction_id'],split=item['split'],fraud=item['fraud'],scenario=item['scenario'],
                       **sub,fraud_score=result['score'],decision=result['decision']))
result=pd.DataFrame(output); result.to_csv(Path(cfg['paths']['reports'])/'fusion_predictions.csv',index=False)
report={'positive_definition':'Any fraudulent transaction. Review OR block is a positive detection; auto-block is also evaluated separately.',
        'weights':cfg['fusion']['weights'],'threshold_selection':'Validation-selected policy: recall-weighted F2 for review and precision constraint for block; see policy_selection.json. Initial policy exploration is retained separately.',
        'dataset_caveat':'Synthetic scenario recovery, not external validation or calibrated fraud probability.'}
for split in ['validation','test']:
    part=result[result.split==split]
    report[split]=metrics(part.fraud,part.fraud_score,cfg['fusion']['review_threshold'])
    report[split+'_auto_block']=metrics(part.fraud,part.fraud_score,cfg['fusion']['block_threshold'])
    report[split+'_scenario_detection']={s:float((g.fraud_score>=cfg['fusion']['review_threshold']).mean()) for s,g in part.groupby('scenario')}
save_report(cfg,'fusion',report)
