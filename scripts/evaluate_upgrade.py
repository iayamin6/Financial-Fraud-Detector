"""Reproducible development evaluation. Scenario tests are not an external benchmark."""
import fraud
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime,timedelta,timezone
import numpy as np
import pandas as pd
from fraud.config import load_config
from fraud.engine import Engine
from fraud.schemas import Transaction
from fraud.behavior import FEATURES,History
from fraud.network import NetworkLayer
from fraud.aml import analyze
from fraud.fusion import fuse
from fraud.evaluation import metrics
from fraud.workflows import Investigations
cfg=load_config()
with TemporaryDirectory() as directory:
 cfg['paths']['database']=str(Path(directory)/'evaluation.sqlite3');engine=Engine(cfg)
 root=Path(cfg['paths']['data']); df=pd.read_csv(root/'transactions.csv').replace({np.nan:None})
 bf=pd.read_csv(root/'behavior_features.csv'); nf=pd.read_csv(root/'network_features.csv')
 mask=df.split=='test'; y=df.loc[mask,'fraud'].astype(int).to_numpy(); b=engine.behavior.bundle
 x=b['scaler'].transform(bf.loc[mask,FEATURES]); supervised=b['xgb'].predict_proba(x)[:,1]
 anomaly=np.clip((-b['isolation'].score_samples(x)-b['q_low'])/(b['q_high']-b['q_low']),0,1)
 behavior=engine.behavior.predict_array(bf.loc[mask,FEATURES]);full=[];no_text=[];cache={}
 for j,(idx,row) in enumerate(df.loc[mask].iterrows()):
  text=row['text']
  if text not in cache:cache[text]=engine.text.score(text)
  t=cache[text];n=engine.network.score(nf.loc[idx].to_dict())['score']
  full.append(fuse({'text':t['score'],'behavioral':float(behavior[j]),'network':n,'rules':t['rules']},cfg)['score'])
  no_text.append(fuse({'text':0.,'behavioral':float(behavior[j]),'network':n,'rules':0.},cfg)['score'])
 texts=pd.read_csv(root/'texts.csv'); texts=texts[texts.split=='test']
 ts=[engine.text.score(t)['score'] for t in texts.text]
 queries=[('How do I investigate an OTP request?','FS-OTP-01'),('Repeated payments just below a threshold','FS-STR-01'),('Multiple sources rapidly forwarding funds','FS-MULE-01'),('Circular transfers between connected accounts','FS-NET-01'),('Unusually frequent transactions and anomaly scores','FS-VEL-01'),('Analyst review and case outcome','FS-REVIEW-01'),('Protecting sensitive information in evidence notes','FS-DATA-01')]
 kb=Investigations(engine).knowledge();retrieval=[]
 for q,expected in queries:
  ids=[d['id'] for d in kb.retrieve(q)];retrieval.append({'query':q,'expected':expected,'retrieved':ids,'hit':expected in ids})
 generated=kb.answer('How should an analyst investigate a request to share an OTP?')
 def tx(name,minute=0,sender='a',recipient='b',amount=100):
  return Transaction(transaction_id=name,sender_id=sender,recipient_id=recipient,amount=amount,account_age_days=200,timestamp=datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=minute))
 scenario_labels=[];scenario_scores=[];scenario_details=[]
 for i in range(20):
  h=History();amount=8100+i*40
  for j in range(2):h.add(tx(f's{i}-{j}',minute=j,amount=amount))
  r=analyze(tx(f's{i}-last',minute=3,amount=amount),h,cfg)
  scenario_labels.append(1);scenario_scores.append(int(any(a['kind']=='structuring' for a in r['alerts'])))
  h=History();h.add(tx(f'l{i}',amount=20+i))
  r=analyze(tx(f'l{i}-last',minute=3,amount=30+i),h,cfg)
  scenario_labels.append(0);scenario_scores.append(int(bool(r['alerts'])))
 report={'scope':'Synthetic development holdout and constructed regression scenarios. No external banking validation.',
         'positive_definition':'Transaction: any synthetic fraud; NLP: any scam class. AML scenarios: constructed structuring pattern, not confirmed money laundering.',
         'nlp':metrics(texts.fraud,ts),'supervised_transaction':metrics(y,supervised),'anomaly':metrics(y,anomaly),
         'behavioral':metrics(y,behavior),'fusion':metrics(y,full,cfg['fusion']['review_threshold']),
         'transaction_network_without_text_same_weights':metrics(y,no_text,cfg['fusion']['review_threshold']),
         'ablation_note':'Fixed original weights and policy; removing text reduces available evidence. Not a separately optimized transaction-only model.',
         'aml_scenario_regression':metrics(scenario_labels,scenario_scores),
         'retrieval':{'recall_at_k':sum(r['hit'] for r in retrieval)/len(retrieval),'queries':retrieval,'note':'Small author-created policy retrieval test, not independent benchmark'},
         'local_llm':{'mode':generated['mode'],'citation_count':len(generated['citations']),'verbatim_grounding':all(c['text'] in generated['answer'] for c in generated['citations'])}}
 Path(cfg['paths']['reports'],'upgrade_evaluation.json').write_text(json.dumps(report,indent=2))
 print(json.dumps({k:v for k,v in report.items() if k not in {'retrieval'}},indent=2))
