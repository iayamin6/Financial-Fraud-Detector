"""Descriptive drift and adjudicated-case evaluation, never automatic retraining."""
import json
import numpy as np
import pandas as pd
from pathlib import Path
from .evaluation import metrics


def psi(reference,current):
    reference=np.asarray(reference,dtype=float);current=np.asarray(current,dtype=float)
    if not len(reference) or not len(current): return None
    edges=np.unique(np.quantile(reference,np.linspace(0,1,11)))
    # Preserve a split even for a constant training feature.
    if len(edges)<2: edges=np.array([reference[0]-.5,reference[0]+.5])
    bins=np.r_[-np.inf,edges,np.inf]
    a=np.histogram(reference,bins)[0].astype(float)+.5;b=np.histogram(current,bins)[0].astype(float)+.5
    a/=a.sum();b/=b.sum()
    return float(np.sum((b-a)*np.log(b/a)))


def monitor(engine):
    c=engine.cfg['monitoring'];records=engine.recent(c['recent_limit'])
    baseline=pd.read_csv(Path(engine.cfg['paths']['data'])/'behavior_features.csv')
    labels=pd.read_csv(Path(engine.cfg['paths']['data'])/'transactions.csv')
    baseline=baseline.loc[labels.split=='train']
    drift={}
    if len(records)>=c['min_samples']:
        for f in ['log_amount','amount_ratio','velocity_count_ratio','new_payee','age_size_ratio']:
            value=psi(baseline[f],[r['layers']['behavioral']['features'][f] for r in records])
            drift[f]={'psi':value,'warning':value>=c['psi_warning']}
    prediction_psi=None
    prediction_path=Path(engine.cfg['paths']['reports'])/'fusion_predictions.csv'
    if len(records)>=c['min_samples'] and prediction_path.exists():
        reference=pd.read_csv(prediction_path)
        prediction_psi=psi(reference.loc[reference.split=='validation','fraud_score'],[r['fraud_score'] for r in records])
    with engine.store.connect() as db:
        verified=db.execute("SELECT c.outcome,s.result_json FROM cases c JOIN scores s USING(transaction_id) WHERE c.status='resolved' AND c.outcome IN ('confirmed_fraud','legitimate')").fetchall()
    y=[int(r['outcome']=='confirmed_fraud') for r in verified]; scores=[json.loads(r['result_json'])['fraud_score'] for r in verified]
    return {'sample_count':len(records),'minimum_samples':c['min_samples'],'feature_drift':drift,
            'status':'ready' if drift else 'insufficient_samples','reference':'Synthetic training partition; not a production population',
            'prediction_psi_against_synthetic_validation':prediction_psi,
            'prediction_distribution':{tier:sum(r['risk_tier']==tier for r in records) for tier in ['low','medium','high']},
            'verified_outcome_metrics':metrics(y,scores,engine.cfg['fusion']['review_threshold']) if y else None,
            'limitations':'Adjudicated cases are selection-biased. Drift is not proof of degraded accuracy. No automatic retraining.',
            'model_version':engine.version}
