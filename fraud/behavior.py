from collections import defaultdict
from datetime import timedelta
from pathlib import Path
import math
import joblib
import numpy as np
import pandas as pd

FEATURES=['log_amount','amount_ratio','hour_sin','hour_cos','velocity_count_ratio','velocity_sum_ratio',
          'new_payee','round_amount','age_size_ratio','device_changed','geo_changed']

class History:
    def __init__(self):
        self.by_sender=defaultdict(list)
        self.events=[]
    def add(self,tx,flag=0.):
        self.by_sender[tx.sender_id].append(tx)
        self.events.append((tx,float(flag)))

def features(tx,history,cfg):
    prior=[p for p in history.by_sender.get(tx.sender_id,[]) if p.timestamp<tx.timestamp]
    recent=[p for p in prior if p.timestamp>=tx.timestamp-timedelta(minutes=cfg['behavior']['window_minutes'])]
    baseline=[p for p in prior if p.timestamp<tx.timestamp-timedelta(minutes=cfg['behavior']['window_minutes'])
              and p.timestamp>=tx.timestamp-timedelta(hours=cfg['behavior']['baseline_hours'])]
    typical=float(np.median([p.amount for p in prior])) if prior else cfg['behavior']['default_amount']
    baseline_duration=max(1.,cfg['behavior']['baseline_hours']-cfg['behavior']['window_minutes']/60)
    hourly=max(cfg['behavior']['default_hourly_count'],len(baseline)/baseline_duration)
    expected=hourly*cfg['behavior']['window_minutes']/60
    last=prior[-1] if prior else None
    hour=tx.timestamp.hour+tx.timestamp.minute/60
    result=dict(log_amount=math.log1p(tx.amount),amount_ratio=tx.amount/max(typical,1),hour_sin=math.sin(hour*math.pi/12),
                hour_cos=math.cos(hour*math.pi/12),velocity_count_ratio=(len(recent)+1)/max(expected,1),
                velocity_sum_ratio=(sum(p.amount for p in recent)+tx.amount)/max(typical*expected,1),
                new_payee=float(not any(p.recipient_id==tx.recipient_id for p in prior)),
                round_amount=float(tx.amount%100==0),age_size_ratio=math.log1p(tx.amount/(tx.account_age_days+1)),
                device_changed=float(bool(last and tx.device_id and last.device_id and tx.device_id!=last.device_id)),
                geo_changed=float(bool(last and tx.country and last.country and tx.country!=last.country)))
    return result

class BehaviorLayer:
    def __init__(self,cfg):
        self.cfg=cfg; self.bundle=joblib.load(Path(cfg['paths']['models'])/'behavior.joblib')
    def predict_array(self,values):
        b=self.bundle; x=b['scaler'].transform(pd.DataFrame(np.asarray(values),columns=FEATURES))
        supervised=b['xgb'].predict_proba(x)[:,1]
        raw=-b['isolation'].score_samples(x)
        anomaly=np.clip((raw-b['q_low'])/max(b['q_high']-b['q_low'],1e-9),0,1)
        w=self.cfg['behavior']['isolation_weight']
        return (1-w)*supervised+w*anomaly
    def score(self,values):
        b=self.bundle; ordered=np.array([[values[k] for k in FEATURES]])
        x=b['scaler'].transform(pd.DataFrame(ordered,columns=FEATURES)); supervised=float(b['xgb'].predict_proba(x)[0,1])
        raw=float(-b['isolation'].score_samples(x)[0]); anomaly=float(np.clip((raw-b['q_low'])/max(b['q_high']-b['q_low'],1e-9),0,1))
        w=self.cfg['behavior']['isolation_weight']
        reasons=[]
        if values['amount_ratio']>=3: reasons.append(f"Amount {values['amount_ratio']:.1f}× sender median")
        if values['velocity_count_ratio']>=3: reasons.append(f"Transaction count {values['velocity_count_ratio']:.1f}× historical rate")
        if values['new_payee']: reasons.append('New payee')
        if values['device_changed']: reasons.append('Device changed')
        if values['geo_changed']: reasons.append('Country changed')
        return dict(score=(1-w)*supervised+w*anomaly,xgboost=supervised,isolation=anomaly,features=values,reasons=reasons)
