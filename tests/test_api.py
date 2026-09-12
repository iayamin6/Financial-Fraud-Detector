import csv
import io
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from api.main import create_app
from fraud.config import load_config

@pytest.fixture(scope='module')
def client(tmp_path_factory):
    cfg=load_config(); cfg['paths']['database']=str(tmp_path_factory.mktemp('api')/'test.sqlite3')
    with TestClient(create_app(cfg)) as c: yield c

def payload(name,**updates):
    p=dict(transaction_id=name,sender_id='alice',recipient_id='bob',amount=100,timestamp='2026-06-01T00:00:00Z',account_age_days=100)
    p.update(updates); return p

def test_score_retry_conflict_and_metrics(client):
    p=payload('idempotent',text='Send your OTP immediately to the agent.')
    first=client.post('/score',json=p); assert first.status_code==200
    body=first.json(); assert body['decision']=='auto_block' and body['sub_scores']['rules']>=.95
    assert client.post('/score',json=p).json()==body
    assert client.post('/score',json={**p,'amount':101}).status_code==409
    assert 'X-Process-Time-Ms' in first.headers
    assert client.get('/metrics').json()['average_latency_ms']['text']>0
    assert client.get('/health').json()['status']=='ready'

@pytest.mark.parametrize('updates',[{'amount':-1},{'amount':float('inf')},{'timestamp':'2026-06-01'}, {'text':'x'*5001},{'fraud':1}])
def test_validation(client,updates):
    if updates.get('amount')==float('inf'):
        assert client.post('/score',content='{"amount":1e999}',headers={'Content-Type':'application/json'}).status_code==422
    else: assert client.post('/score',json=payload('invalid',**updates)).status_code==422

def test_list_and_csv_batch_and_rejection(client):
    p=[payload('batch-b'),payload('batch-a')]
    r=client.post('/score/batch',json=p); assert r.status_code==200
    assert [x['transaction_id'] for x in r.json()]==['batch-b','batch-a']
    assert client.post('/score/batch',json=[p[0],p[0]]).status_code==409
    assert client.post('/score/batch',json=[]).status_code==422
    assert client.post('/score/batch',json={'transactions':[payload('wrapped')]}).status_code==200
    output=io.StringIO(); record=payload('csv-a'); writer=csv.DictWriter(output,fieldnames=record);writer.writeheader();writer.writerow(record)
    assert client.post('/score/batch/csv',files={'file':('demo.csv',output.getvalue(),'text/csv')}).status_code==200
    assert client.post('/score/batch/csv',files={'file':('bad.csv','amount,amount\n1,2','text/csv')}).status_code==422
    assert client.post('/score/batch/csv',files={'file':('large.csv',b'x'*2000001,'text/csv')}).status_code==413
    assert client.post('/score',json=payload('late',timestamp='2026-05-01T00:00:00Z')).status_code==409

def test_explain_feedback_and_unknown(client):
    client.post('/score',json=payload('explain',text='Send your OTP to the support agent.'))
    r=client.post('/explain/explain'); assert r.status_code==200
    e=r.json(); assert e['methods']['behavioral']['reconstruction_error']<1e-6
    assert e['methods']['text']['method'].startswith('Exact')
    assert client.post('/explain/explain').json()==e
    r=client.post('/feedback',json={'transaction_id':'explain','correct_label':0}); assert r.status_code==200
    assert r.json()['classification']=='false_positive'
    assert client.post('/feedback',json={'transaction_id':'missing','correct_label':1}).status_code==404
    assert client.post('/explain/missing').status_code==404
    assert client.post('/feedback',json={'transaction_id':'explain','correct_label':2}).status_code==422

def test_duplicate_concurrency_is_exactly_once(client):
    before=client.get('/metrics').json()['scored_transactions']
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses=list(pool.map(lambda _:client.post('/score',json=payload('concurrent')),range(4)))
    assert all(r.status_code==200 for r in responses)
    assert all(r.json()==responses[0].json() for r in responses)
    assert client.get('/metrics').json()['scored_transactions']==before+1

def test_batch_rollback_on_inference_failure(client,monkeypatch):
    engine=client.app.state.engine; original=engine._score; before=client.get('/metrics').json()['scored_transactions']
    def fail_second(tx,history):
        if tx.transaction_id=='rollback-b': raise RuntimeError('simulated inference failure')
        return original(tx,history)
    monkeypatch.setattr(engine,'_score',fail_second)
    with pytest.raises(RuntimeError): client.post('/score/batch',json=[payload('rollback-a'),payload('rollback-b')])
    assert client.get('/metrics').json()['scored_transactions']==before
