import fraud  # Set native thread limits before importing numerical libraries.
"""Select operating thresholds from validation only; never inspect test labels here."""
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
from fraud.config import load_config,ROOT
from fraud.evaluation import metrics,save_report
cfg=load_config(); root=Path(cfg['paths']['reports'])
df=pd.read_csv(root/'fusion_predictions.csv'); val=df[df.split=='validation']
candidates=[metrics(val.fraud,val.fraud_score,round(float(t),3)) for t in np.linspace(.05,.95,181)]
for m in candidates:
    m['f2']=5*m['precision']*m['recall']/max(4*m['precision']+m['recall'],1e-12)
best=max(candidates,key=lambda m:(m['f2'],m['precision'],m['threshold']))
block=[m for m in candidates if m['threshold']>best['threshold'] and m['precision']>=.95 and sum(row[1] for row in m['confusion_matrix'])>=5]
block_threshold=min((m['threshold'] for m in block),default=.99)
config_path=Path(__import__('os').getenv('FRAUD_CONFIG',ROOT/'config.yaml'))
raw=yaml.safe_load(config_path.read_text()); raw['fusion']['review_threshold']=best['threshold']; raw['fusion']['block_threshold']=block_threshold
config_path.write_text(yaml.safe_dump(raw,sort_keys=False))
save_report(cfg,'policy_selection',{'method':'Maximize validation F2 (recall weighted) for review; lowest higher threshold with >=95% validation precision and >=5 predicted positives for block, otherwise .99.',
 'validation_review':best,'block_threshold':block_threshold,'test_labels_used':False})
