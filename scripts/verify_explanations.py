import fraud
import json
from pathlib import Path
import numpy as np
import pandas as pd
from fraud.config import load_config
from fraud.text import TextLayer
from fraud.behavior import BehaviorLayer,FEATURES
from fraud.explain import Explainer
from fraud.schemas import Transaction
cfg=load_config(); text=TextLayer(cfg); behavior=BehaviorLayer(cfg)
df=pd.read_csv(Path(cfg['paths']['data'])/'transactions.csv').replace({np.nan:None})
bf=pd.read_csv(Path(cfg['paths']['data'])/'behavior_features.csv')
item=df.iloc[-1].to_dict(); tx=Transaction.model_validate({k:v for k,v in item.items() if k in Transaction.model_fields})
tx.text='Your grocery purchase was completed. Thank you.'
b=behavior.score(bf.iloc[-1].to_dict()); t=text.score(tx.text)
result=dict(model_version='explanation-verification',sub_scores={'behavioral':b['score']},layers={'behavioral':b,'text':t,'network':{}},fusion={},reasons=[])
r=Explainer(cfg,text,behavior).explain(tx,result)
assert r['methods']['behavioral']['reconstruction_error']<1e-6
assert r['methods']['text']['method'].startswith('LIME')
(Path(cfg['paths']['reports'])/'explanation_verification.json').write_text(json.dumps(r,indent=2))
print('SHAP reconstructed combined behavior score; full routed text LIME executed successfully.')
