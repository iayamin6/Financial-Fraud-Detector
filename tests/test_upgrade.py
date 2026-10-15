from datetime import datetime,timedelta,timezone
from pathlib import Path
import copy
import json
import pytest
from fraud.config import load_config
from fraud.schemas import Transaction
from fraud.behavior import History
from fraud.aml import analyze
from fraud.text import rule_signals
from fraud.engine import Engine,Conflict
from fraud.cases import Cases,CaseUpdate,Review
from fraud.workflows import Investigations
from fraud.monitoring import psi,monitor
from fraud.store import Store


def tx(name,sender='a',recipient='b',amount=100,minute=0,text=None):
    return Transaction(transaction_id=name,sender_id=sender,recipient_id=recipient,amount=amount,
                       timestamp=datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=minute),account_age_days=200,text=text)

@pytest.fixture(scope='module')
def base(tmp_path_factory):
    cfg=load_config();cfg['paths']['database']=str(tmp_path_factory.mktemp('upgrade')/'base.sqlite3')
    cfg['rag']['generator_enabled']=False
    return Engine(cfg)

@pytest.fixture
def engine(base,tmp_path):
    engine=copy.copy(base);engine.store=Store(tmp_path/'cases.sqlite3');return engine


def test_aml_structuring_and_point_in_time():
    cfg=load_config();h=History()
    h.add(tx('one',amount=9000));h.add(tx('two',amount=9500,minute=1))
    h.add(tx('future',amount=9500,minute=99))
    result=analyze(tx('three',amount=9800,minute=2),h,cfg)
    alert=next(a for a in result['alerts'] if a['kind']=='structuring')
    assert alert['transaction_ids']==['one','three','two']
    assert not analyze(tx('normal',amount=150,minute=3),History(),cfg)['alerts']


def test_mule_and_cycle():
    cfg=load_config();h=History()
    for i in range(3):h.add(tx('in'+str(i),sender='source'+str(i),recipient='mule',amount=100,minute=i))
    kinds={a['kind'] for a in analyze(tx('out',sender='mule',recipient='sink',amount=290,minute=4),h,cfg)['alerts']}
    assert {'mule_indicator','rapid_movement'}<=kinds
    h=History();h.add(tx('ab',sender='a',recipient='b'));h.add(tx('bc',sender='b',recipient='c',minute=1))
    result=analyze(tx('ca',sender='c',recipient='a',minute=2),h,cfg)
    assert result['cycle_path']==['a','b','c']
    assert 'circular_transfer' in {a['kind'] for a in result['alerts']}


def test_bangla_and_advisories():
    cfg=load_config()
    assert rule_signals('আপনার OTP এখনই পাঠান',cfg)[0]
    assert rule_signals('OTP share korun',cfg)[0]
    assert not rule_signals('Never share your OTP.',cfg)[0]
    assert not rule_signals('OTP share korben na',cfg)[0]
    assert not rule_signals('ওটিপি দেবেন না',cfg)[0]
    assert rule_signals('Never share your OTP. Send your PIN to this agent.',cfg)[0]


def test_atomic_cases_retry_and_revision(engine):
    t=tx('scam',text='Send your OTP now.')
    engine.score_many([t]);engine.score_many([t]);cases=Cases(engine)
    assert len(cases.list())==1
    c=cases.list()[0]
    assert cases.create('scam','analyst')['case_id']==c['case_id']
    changed=cases.update(c['case_id'],CaseUpdate(revision=0,status='under_review',note='Reviewing'),'analyst')
    assert changed['revision']==1
    with pytest.raises(Conflict): cases.update(c['case_id'],CaseUpdate(revision=0,note='stale'),'analyst')
    with pytest.raises(ValueError): cases.update(c['case_id'],CaseUpdate(revision=1,status='resolved'),'analyst')
    assert len(changed['history'])==2


def test_workflow_survives_reconstruction_and_human_review(engine):
    engine.score_many([tx('investigate',text='Send your OTP now.')]);cases=Cases(engine);cid=cases.list()[0]['case_id']
    service=Investigations(engine);run=service.start(cid,'analyst-a')
    assert run['status']=='awaiting_review',run
    assert run['result']['report']['guidance']['citations']
    assert service.start(cid,'analyst-a')['run_id']==run['run_id']
    restarted=copy.copy(engine);restarted.store=Store(engine.store.path)
    c=Cases(restarted).get(cid)
    result=Investigations(restarted).resume(run['run_id'],Review(outcome='inconclusive',note='Need independent evidence',revision=c['revision']),'analyst-b')
    assert result['status']=='completed',result
    case=Cases(restarted).get(cid)
    assert case['status']=='resolved' and case['outcome']=='inconclusive'
    assert case['history'][-1]['actor']=='analyst-b'
    assert monitor(engine)['verified_outcome_metrics'] is None
    with pytest.raises(Conflict): Investigations(restarted).resume(run['run_id'],Review(outcome='legitimate',note='again',revision=case['revision']),'analyst-b')


def test_case_and_checkpoint_isolation(engine,tmp_path):
    engine.score_many([tx('private',text='Send your OTP now.')]);cid=Cases(engine).list()[0]['case_id']
    other=copy.copy(engine);other.store=Store(tmp_path/'other.sqlite3')
    assert Cases(other).list()==[]
    with pytest.raises(ValueError):Cases(other).get(cid)


def test_retrieval_citations_and_abstention(engine):
    kb=Investigations(engine).knowledge()
    answer=kb.answer('How should repeated transfers just below a threshold be investigated?')
    assert 'FS-STR-01' in {c['id'] for c in answer['citations']}
    assert all(c['text'] in answer['answer'] for c in answer['citations'])
    original=kb.cfg['rag']['min_similarity'];kb.cfg['rag']['min_similarity']=1.1
    try: assert kb.answer('unrelated request')['mode']=='insufficient_evidence'
    finally:kb.cfg['rag']['min_similarity']=original


def test_drift_and_verified_labels(engine):
    assert psi([1,2,3,4],[1,2,3,4])==pytest.approx(0)
    assert psi([1]*100,[100]*100)>.2
    assert monitor(engine)['status']=='insufficient_samples'
    engine.score_many([tx('review',text='Send your OTP now.')]);cases=Cases(engine);cid=cases.list()[0]['case_id']
    c=cases.update(cid,CaseUpdate(revision=0,status='under_review'),'analyst')
    cases.update(cid,CaseUpdate(revision=c['revision'],status='resolved',outcome='confirmed_fraud',note='Synthetic scenario verified'),'analyst')
    assert monitor(engine)['verified_outcome_metrics']['positives']==1


def test_api_auth_and_case_routes(base,monkeypatch,tmp_path):
    from fastapi.testclient import TestClient
    from api.main import create_app
    import api.main
    monkeypatch.setattr(api.main,'Engine',lambda cfg:base)
    cfg=copy.deepcopy(base.cfg);cfg['security']['mode']='authenticated'
    analyst='a'*32;viewer='v'*32;scorer='s'*32
    monkeypatch.setenv('FRAUD_API_KEYS',json.dumps({analyst:{'actor':'alice','role':'analyst'},viewer:{'actor':'bob','role':'viewer'},scorer:{'actor':'ingest','role':'scorer'}}))
    with TestClient(create_app(cfg)) as client:
        assert client.get('/health').status_code==200
        assert client.get('/cases').status_code==401
        assert client.get('/cases',headers={'X-API-Key':scorer}).status_code==403
        assert client.post('/score',json=tx('api-scam',text='Send your OTP now.').model_dump(mode='json'),headers={'X-API-Key':scorer}).status_code==200
        c=client.get('/cases',headers={'X-API-Key':analyst}).json()[0]
        assert client.patch('/cases/'+c['case_id'],json={'revision':0,'status':'under_review'},headers={'X-API-Key':viewer}).status_code==403
        assert client.patch('/cases/'+c['case_id'],json={'revision':0,'status':'under_review'},headers={'X-API-Key':analyst}).status_code==200
        assert client.get('/monitoring',headers={'X-API-Key':analyst}).status_code==200


def test_retrieval_failure_still_requires_human(engine,monkeypatch):
    engine.score_many([tx('rag-failure',text='Send your OTP now.')]);cid=Cases(engine).list()[0]['case_id']
    def broken(self):raise RuntimeError('simulated retrieval unavailable')
    monkeypatch.setattr(Investigations,'knowledge',broken)
    result=Investigations(engine).start(cid,'analyst')
    assert result['status']=='awaiting_review'
    assert result['result']['report']['guidance']['mode']=='retrieval_failed'
    assert Cases(engine).get(cid)['status']=='under_review'


def test_interrupted_workflow_retry(engine,monkeypatch):
    engine.score_many([tx('retry',text='Send your OTP now.')]);cases=Cases(engine);cid=cases.list()[0]['case_id']
    # Inject a failure inside graph execution, after case setup.
    service=Investigations(engine)
    original_build=service.build
    def broken_build(saver,actor):
        graph=original_build(saver,actor)
        def fail(*args,**kwargs):raise RuntimeError('simulated interrupted process')
        graph.invoke=fail
        return graph
    monkeypatch.setattr(service,'build',broken_build)
    first=service.start(cid,'analyst')
    assert first['status']=='failed'
    recovered=Investigations(engine).execute(first['run_id'],'analyst')
    assert recovered['status']=='awaiting_review',recovered


def test_scoring_rollback_includes_cases(engine,monkeypatch):
    original=engine._score
    def score(t,h):
        if t.transaction_id=='fail':raise RuntimeError('inference failed')
        return original(t,h)
    monkeypatch.setattr(engine,'_score',score)
    with pytest.raises(RuntimeError):engine.score_many([tx('first',text='Send your OTP'),tx('fail',minute=1)])
    assert not engine.recent() and not Cases(engine).list()
