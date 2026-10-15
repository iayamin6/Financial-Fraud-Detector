"""Durable LangGraph investigations with explicit analyst interruption."""
import json
import os
from typing import TypedDict
from uuid import uuid4
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.sqlite import SqliteSaver
from .cases import Cases, CaseUpdate, now, event
from .engine import Conflict, NotFound
from .rag import Knowledge

os.environ.setdefault('LANGGRAPH_STRICT_MSGPACK','true')

class State(TypedDict, total=False):
    case_id: str
    evidence: dict
    findings: dict
    guidance: dict
    report: dict
    review: dict
    result: dict


class Investigations:
    def __init__(self, engine): self.engine=engine;self.cases=Cases(engine)
    def knowledge(self):
        # Per-engine model resource, never stores visitor transactions.
        if not hasattr(self.engine,'knowledge'): self.engine.knowledge=Knowledge(self.engine)
        return self.engine.knowledge
    def build(self, saver, actor):
        graph=StateGraph(State)
        def collect(s):
            c=self.cases.get(s['case_id'])
            # Persist original score snapshot, not predictions from current weights.
            return {'evidence':{'transaction_id':c['transaction_id'],'score':c['score'],'revision':c['revision']}}
        def models(s):
            b=s['evidence']['score']['layers']['behavioral']
            return {'findings':{'supervised':b['xgboost'],'anomaly':b['isolation'],'interpretation':'Uncalibrated scores; anomaly alone is not fraud.'}}
        def relationships(s):
            score=s['evidence']['score']; f=dict(s['findings'])
            f['network']=score['layers']['network']; f['aml']=score['layers'].get('aml',{'alerts':[],'note':'AML unavailable for legacy prediction'})
            return {'findings':f}
        def retrieve(s):
            kinds=[a['kind'] for a in s['findings']['aml']['alerts']]
            question='Investigation guidance for '+', '.join(kinds or s['evidence']['score']['reasons'])
            try: return {'guidance':self.knowledge().answer(question[:1000])}
            except Exception: return {'guidance':{'answer':'Retrieval unavailable. Human review requires additional evidence.','citations':[],'mode':'retrieval_failed'}}
        def generic(s):
            return {'guidance':{'answer':'No strong configured indicators. Review the original evidence before deciding.','citations':[],'mode':'not_required'}}
        def report(s):
            return {'report':{'title':'FraudShield investigation draft','transaction_id':s['evidence']['transaction_id'],
                              'model_version':s['evidence']['score']['model_version'],'findings':s['findings'],'guidance':s['guidance'],
                              'limitations':['Synthetic-data models; uncalibrated risk scores.','Graph/AML indicators are unconfirmed.','Human review required; no funds blocked or regulatory reports submitted.']}}
        def review(s):
            response=interrupt({'report':s['report'],'required':'Authorized analyst outcome and rationale'})
            # Actor comes from the authenticated caller, never model output.
            body=CaseUpdate(revision=response['revision'],status='resolved',outcome=response['outcome'],note=response['note'])
            c=self.cases.get(s['case_id'])
            if c['status']=='resolved':
                # A worker can restart after the DB commit but before its checkpoint.
                with self.engine.store.connect() as db:
                    prior=db.execute("SELECT detail_json FROM case_events WHERE case_id=? AND action='workflow_review' ORDER BY id DESC LIMIT 1",(s['case_id'],)).fetchone()
                if not prior or json.loads(prior[0])!=response: raise Conflict('Case already resolved by another review')
                return {'review':response,'result':{'case_id':c['case_id'],'outcome':c['outcome']}}
            # Update + audit atomically, with optimistic revision enforcement.
            with self.engine.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row=db.execute('SELECT * FROM cases WHERE case_id=?',(s['case_id'],)).fetchone()
                if row['revision']!=body.revision or row['status']!='under_review': raise Conflict('Case changed; reload before review')
                db.execute("UPDATE cases SET status='resolved',outcome=?,revision=revision+1,updated_at=? WHERE case_id=?",(body.outcome,now(),s['case_id']))
                event(db,s['case_id'],actor,'workflow_review',response)
            return {'review':response,'result':{'case_id':s['case_id'],'outcome':body.outcome}}
        for name,fn in [('collect',collect),('models',models),('relationships',relationships),('retrieve',retrieve),('generic',generic),('report',report),('human_review',review)]: graph.add_node(name,fn)
        graph.add_edge(START,'collect');graph.add_edge('collect','models');graph.add_edge('models','relationships')
        graph.add_conditional_edges('relationships',lambda s:'retrieve' if s['findings']['aml']['alerts'] or s['evidence']['score']['decision']!='auto_pass' else 'generic')
        graph.add_edge('retrieve','report');graph.add_edge('generic','report');graph.add_edge('report','human_review');graph.add_edge('human_review',END)
        return graph.compile(checkpointer=saver)
    def start(self,cid,actor):
        with self.engine.lock:
            c=self.cases.get(cid)
            if c['status']=='resolved': raise Conflict('Case is resolved')
            with self.engine.store.connect() as db:
                prior=db.execute("SELECT run_id FROM investigations WHERE case_id=? AND status!='completed' ORDER BY created_at DESC LIMIT 1",(cid,)).fetchone()
            if prior: return self.get(prior[0])
            if c['status']=='open': self.cases.update(cid,CaseUpdate(revision=c['revision'],status='under_review'),actor)
            rid='run-'+uuid4().hex
            with self.engine.store.connect() as db:
                db.execute('INSERT INTO investigations VALUES(?,?,?,?,?,?,?)',(rid,cid,'running',None,None,now(),now()))
                event(db,cid,actor,'investigation_started',{'run_id':rid})
            return self.execute(rid,actor,{'case_id':cid})
    def get(self,rid):
        with self.engine.store.connect() as db: row=db.execute('SELECT * FROM investigations WHERE run_id=?',(rid,)).fetchone()
        if not row: raise NotFound('Investigation not found')
        return {**dict(row),'result':json.loads(row['result_json']) if row['result_json'] else None}
    def execute(self,rid,actor,value=None):
        run=self.get(rid)
        if run['status']=='completed': return run
        with self.engine.lock, SqliteSaver.from_conn_string(self.engine.store.path+'.checkpoints.sqlite') as saver:
            graph=self.build(saver,actor); config={'configurable':{'thread_id':rid}}
            try:
                if value is None:
                    snapshot=graph.get_state(config)
                    if not snapshot.values: value={'case_id':run['case_id']}
                    elif any(t.interrupts for t in snapshot.tasks):
                        with self.engine.store.connect() as db:
                            db.execute('UPDATE investigations SET status=?,result_json=?,error=NULL,updated_at=? WHERE run_id=?',('awaiting_review',json.dumps(dict(snapshot.values)),now(),rid))
                        return self.get(rid)
                result=graph.invoke(value,config)
                snapshot=graph.get_state(config)
                status='awaiting_review' if any(t.interrupts for t in snapshot.tasks) else 'completed'
                serial=dict(snapshot.values)
                with self.engine.store.connect() as db:
                    db.execute('UPDATE investigations SET status=?,result_json=?,error=NULL,updated_at=? WHERE run_id=?',(status,json.dumps(serial),now(),rid))
            except Exception as exc:
                with self.engine.store.connect() as db:
                    db.execute('UPDATE investigations SET status=?,error=?,updated_at=? WHERE run_id=?',('failed',type(exc).__name__+': workflow interrupted; retry or reload case',now(),rid))
        return self.get(rid)
    def resume(self,rid,body,actor):
        with self.engine.lock:
            run=self.get(rid)
            if run['status']!='awaiting_review': raise Conflict('Investigation is not awaiting review')
            c=self.cases.get(run['case_id'])
            if c['revision']!=body.revision or c['status']!='under_review': raise Conflict('Case changed; reload before reviewing')
            return self.execute(rid,actor,Command(resume=body.model_dump()))
