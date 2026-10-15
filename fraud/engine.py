import hashlib
import json
import logging
from pathlib import Path
from datetime import datetime,timezone
from threading import RLock
from time import perf_counter
from .text import TextLayer
from .behavior import BehaviorLayer,History,features as behavior_features
from .network import NetworkLayer,features as network_features
from .fusion import fuse
from .aml import analyze as analyze_aml
from .explain import Explainer
from .store import Store
from .schemas import Transaction,ScoreResponse

logger=logging.getLogger('fraud.latency')
class Conflict(ValueError): pass
class NotFound(ValueError): pass

def canonical(tx): return json.dumps(tx.model_dump(mode='json'),sort_keys=True,separators=(',',':'))

class Engine:
    def __init__(self,cfg):
        self.cfg=cfg; self.lock=RLock(); self.store=Store(cfg['paths']['database'])
        self.text=TextLayer(cfg); self.behavior=BehaviorLayer(cfg); self.network=NetworkLayer(cfg)
        self.explainer=Explainer(cfg,self.text,self.behavior)
        digest=hashlib.sha256(json.dumps({k:v for k,v in cfg.items() if k!='paths'},sort_keys=True).encode())
        for path in sorted(Path(cfg['paths']['models']).rglob('*')):
            if path.is_file() and '.cache' not in path.parts:
                digest.update(str(path.relative_to(cfg['paths']['models'])).encode())
                with path.open('rb') as f:
                    for chunk in iter(lambda:f.read(1024*1024),b''): digest.update(chunk)
        for path in sorted(Path(__file__).parent.glob('*.py')): digest.update(path.read_bytes())
        self.version=digest.hexdigest()[:16]
        from .mlops import manifest
        self.component_versions={k:v['sha256'] for k,v in manifest(cfg).items()}

    def _score(self,tx,history):
        start=perf_counter(); timings={}
        def timed(name,fn):
            t=perf_counter(); result=fn(); timings[name]=(perf_counter()-t)*1000; return result
        text=timed('text',lambda:self.text.score(tx.text))
        behavior=timed('behavioral',lambda:self.behavior.score(behavior_features(tx,history,self.cfg)))
        network=timed('network',lambda:self.network.score(network_features(tx,history,self.cfg)))
        aml=timed('aml',lambda:analyze_aml(tx,history,self.cfg))
        sub=dict(text=text['score'],behavioral=behavior['score'],network=network['score'],rules=text['rules'])
        fusion=timed('fusion',lambda:fuse(sub,self.cfg))
        reasons=behavior['reasons']+network['reasons']+[s['detail'] for s in text['signals'] if s['name'] not in {'semantic_match','mixed_scripts'} and s['value']>=.5]
        if fusion['rule_override_delta']>0: reasons.insert(0,'High-confidence credential request triggered the explicit rule floor')
        if not reasons: reasons=['No strong configured signals; see per-layer scores and model explanation']
        timings['total_pipeline']=(perf_counter()-start)*1000
        result=ScoreResponse(transaction_id=tx.transaction_id,fraud_score=fusion['score'],risk_tier=fusion['tier'],decision=fusion['decision'],
            sub_scores=sub,reasons=reasons,layers=dict(text=text,behavioral=behavior,network=network,aml=aml),fusion=fusion,latency_ms=timings,
            component_versions=self.component_versions,aml_review_required=aml['requires_review'],model_version=self.version,scored_at=datetime.now(timezone.utc)).model_dump(mode='json')
        logger.info('scoring_latency_ms %s',json.dumps(timings))
        return result

    def score_many(self,transactions):
        if not transactions or len(transactions)>self.cfg['api']['batch_limit']:
            raise ValueError(f"Batch size must be 1..{self.cfg['api']['batch_limit']}")
        ids=[t.transaction_id for t in transactions]
        if len(ids)!=len(set(ids)): raise Conflict('Duplicate transaction IDs within batch')
        with self.lock, self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows=db.execute('SELECT * FROM scores ORDER BY timestamp,transaction_id').fetchall()
            existing={r['transaction_id']:r for r in rows}; result={}; new=[]
            last=max((Transaction.model_validate_json(r['request_json']).timestamp for r in rows),default=None)
            # Prevalidate the entire batch before inference and database mutations.
            for tx in transactions:
                if tx.transaction_id in existing:
                    row=existing[tx.transaction_id]
                    if canonical(tx)!=row['request_json']: raise Conflict(f'ID {tx.transaction_id} already has a different payload')
                    result[tx.transaction_id]=json.loads(row['result_json'])
                elif last is not None and tx.timestamp<last:
                    raise Conflict('Out-of-order event; this real-time demo requires nondecreasing event times. Replay into a fresh database for historical batches.')
                else: new.append(tx)
            history=History()
            for row in rows:
                old=json.loads(row['result_json']); tx=Transaction.model_validate_json(row['request_json'])
                history.add(tx,float(old['sub_scores']['rules']>=self.cfg['nlp']['rule_short_circuit']))
            for tx in sorted(new,key=lambda x:(x.timestamp,x.transaction_id)):
                scored=self._score(tx,history)
                db.execute('INSERT INTO scores(transaction_id,timestamp,request_json,result_json) VALUES(?,?,?,?)',
                           (tx.transaction_id,tx.timestamp.isoformat(),canonical(tx),json.dumps(scored)))
                if self.cfg['cases']['auto_create'] and (scored['decision']!='auto_pass' or scored['layers']['aml']['requires_review']):
                    from .cases import create_in_db
                    create_in_db(db,tx.transaction_id,'system')
                history.add(tx,float(scored['sub_scores']['rules']>=self.cfg['nlp']['rule_short_circuit']))
                result[tx.transaction_id]=scored
            return [result[t.transaction_id] for t in transactions]

    def recent(self,limit=100):
        with self.store.connect() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT result_json FROM scores ORDER BY timestamp DESC,transaction_id DESC LIMIT ?',(limit,))]

    def explain(self,transaction_id):
        with self.lock,self.store.connect() as db:
            row=db.execute('SELECT * FROM scores WHERE transaction_id=?',(transaction_id,)).fetchone()
            if row is None: raise NotFound('Transaction not found')
            if row['explanation_json']: return json.loads(row['explanation_json'])
            result=json.loads(row['result_json'])
            if result['model_version']!=self.version: raise Conflict('Original model/config version is unavailable; cannot explain with different artifacts')
            explanation=self.explainer.explain(Transaction.model_validate_json(row['request_json']),result)
            db.execute('UPDATE scores SET explanation_json=? WHERE transaction_id=?',(json.dumps(explanation),transaction_id))
            return explanation

    def feedback(self,feedback):
        with self.store.connect() as db:
            row=db.execute('SELECT result_json FROM scores WHERE transaction_id=?',(feedback.transaction_id,)).fetchone()
            if row is None: raise NotFound('Transaction not found')
            positive=json.loads(row['result_json'])['decision']!='auto_pass'
            category=('confirmed_fraud' if positive else 'false_negative') if feedback.correct_label else ('false_positive' if positive else 'confirmed_legitimate')
            db.execute('INSERT INTO feedback(transaction_id,correct_label,classification,comment,created_at) VALUES(?,?,?,?,?)',
                       (feedback.transaction_id,feedback.correct_label,category,feedback.comment,datetime.now(timezone.utc).isoformat()))
            return dict(transaction_id=feedback.transaction_id,correct_label=feedback.correct_label,classification=category)

    def metrics(self):
        with self.store.connect() as db:
            rows=[json.loads(r[0]) for r in db.execute('SELECT result_json FROM scores')]
        names=['text','behavioral','network','aml','fusion','total_pipeline']
        return dict(scored_transactions=len(rows),average_latency_ms={k:sum(r['latency_ms'].get(k,0) for r in rows)/len(rows) if rows else 0. for k in names},
                    scope='Persisted unique scores; pipeline timings exclude DB I/O, HTTP and on-demand explanations. HTTP latency is separately logged.',model_version=self.version)
