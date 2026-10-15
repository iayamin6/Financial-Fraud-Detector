"""Transactional case records and append-only application audit events."""
import json
from datetime import datetime, timezone
from uuid import uuid4
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .engine import Conflict, NotFound


def now(): return datetime.now(timezone.utc).isoformat()

class CaseCreate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    transaction_id: str=Field(min_length=1,max_length=128)

class CaseUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision: int=Field(ge=0)
    status: Literal['open','under_review','resolved']|None=None
    assigned_to: str|None=Field(default=None,max_length=128)
    note: str|None=Field(default=None,min_length=1,max_length=2000)
    outcome: Literal['confirmed_fraud','legitimate','inconclusive']|None=None

class Question(BaseModel):
    model_config=ConfigDict(extra='forbid')
    question: str=Field(min_length=3,max_length=1000)

class Review(BaseModel):
    model_config=ConfigDict(extra='forbid')
    outcome: Literal['confirmed_fraud','legitimate','inconclusive']
    note: str=Field(min_length=3,max_length=2000)
    revision: int=Field(ge=0)


def event(db, case_id, actor, action, detail):
    db.execute('INSERT INTO case_events(case_id,actor,action,detail_json,created_at) VALUES(?,?,?,?,?)',
               (case_id,actor,action,json.dumps(detail),now()))


def create_in_db(db, txid, actor):
    row=db.execute('SELECT case_id FROM cases WHERE transaction_id=?',(txid,)).fetchone()
    if row: return row['case_id']
    if not db.execute('SELECT 1 FROM scores WHERE transaction_id=?',(txid,)).fetchone(): raise NotFound('Transaction not found')
    cid='case-'+uuid4().hex; stamp=now()
    db.execute('INSERT INTO cases(case_id,transaction_id,created_at,updated_at) VALUES(?,?,?,?)',(cid,txid,stamp,stamp))
    event(db,cid,actor,'created',{'transaction_id':txid})
    return cid


class Cases:
    def __init__(self,engine): self.engine=engine; self.store=engine.store
    def create(self,txid,actor):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE'); cid=create_in_db(db,txid,actor)
        return self.get(cid)
    def list(self,limit=100):
        with self.store.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM cases ORDER BY updated_at DESC LIMIT ?',(limit,))]
    def get(self,cid):
        with self.store.connect() as db:
            row=db.execute('SELECT * FROM cases WHERE case_id=?',(cid,)).fetchone()
            if not row: raise NotFound('Case not found')
            result=dict(row)
            score=db.execute('SELECT request_json,result_json,explanation_json FROM scores WHERE transaction_id=?',(row['transaction_id'],)).fetchone()
            # Evidence details belong only to the authorized analyst/session.
            result['transaction']=json.loads(score['request_json']);result['score']=json.loads(score['result_json'])
            result['explanation']=json.loads(score['explanation_json']) if score['explanation_json'] else None
            result['history']=[{**dict(r),'detail':json.loads(r['detail_json'])} for r in db.execute('SELECT * FROM case_events WHERE case_id=? ORDER BY id',(cid,))]
            result['investigations']=[dict(r) for r in db.execute('SELECT run_id,status,error,updated_at FROM investigations WHERE case_id=? ORDER BY created_at DESC',(cid,))]
            return result
    def update(self,cid,body,actor):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM cases WHERE case_id=?',(cid,)).fetchone()
            if not row: raise NotFound('Case not found')
            if row['revision']!=body.revision: raise Conflict('Case changed; reload before editing')
            status=body.status or row['status']; outcome=body.outcome or row['outcome']
            if status not in {'open':{'open','under_review'},'under_review':{'under_review','resolved'},'resolved':{'resolved'}}[row['status']]:
                raise Conflict('Invalid case status transition')
            if row['status']=='resolved': raise Conflict('Resolved cases are immutable; retain original adjudication')
            if status=='resolved' and db.execute("SELECT 1 FROM investigations WHERE case_id=? AND status!='completed'",(cid,)).fetchone():
                raise Conflict('Resolve this case through the active workflow review')
            if status=='resolved' and not outcome: raise ValueError('Resolved cases require an outcome')
            if body.outcome and status!='resolved': raise ValueError('Outcome requires resolved status')
            if status=='resolved' and not body.note: raise ValueError('Resolution requires an analyst note')
            assigned=body.assigned_to if body.assigned_to is not None else row['assigned_to']
            db.execute('UPDATE cases SET status=?,outcome=?,assigned_to=?,revision=revision+1,updated_at=? WHERE case_id=?',
                       (status,outcome,assigned,now(),cid))
            event(db,cid,actor,'updated',body.model_dump(exclude_none=True))
        return self.get(cid)

# Explicit response contracts for the investigation API.
class CaseSummary(BaseModel):
    case_id: str
    transaction_id: str
    status: Literal['open','under_review','resolved']
    assigned_to: str|None
    outcome: Literal['confirmed_fraud','legitimate','inconclusive']|None
    revision: int
    created_at: str
    updated_at: str

class CaseDetail(CaseSummary):
    transaction: dict
    score: dict
    explanation: dict|None
    history: list[dict]
    investigations: list[dict]

class RunResponse(BaseModel):
    run_id: str
    case_id: str
    status: Literal['running','failed','awaiting_review','completed']
    result_json: str|None
    error: str|None
    created_at: str
    updated_at: str
    result: dict|None

class GuidanceResponse(BaseModel):
    answer: str
    citations: list[dict]
    mode: str
    generated: bool
    notice: str|None=None
    generation_scope: str|None=None
