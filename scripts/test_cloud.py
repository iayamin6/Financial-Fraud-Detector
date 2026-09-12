from pathlib import Path
from streamlit.testing.v1 import AppTest
root=Path(__file__).resolve().parents[1]
a=AppTest.from_file(str(root/'streamlit_app.py'),default_timeout=120).run()
assert not a.exception, a.exception
a.button(key='demo_normal').click().run()
assert not a.exception, a.exception
assert a.session_state['demo_result']['risk_tier']=='low'
a.button(key='demo_scam').click().run()
assert a.session_state['demo_result']['risk_tier']=='high'
a.button(key='system_check').click().run(timeout=120)
assert not a.exception, a.exception
assert all(passed for _,passed in a.session_state['system_checks'])
b=AppTest.from_file(str(root/'streamlit_app.py'),default_timeout=120).run()
assert not b.exception, b.exception
assert b.session_state['_visitor_engine'].recent(100)==[]
assert len(a.session_state['_visitor_engine'].recent(100))>=4
from dashboard.embedded import dispatch
rows=dispatch(b.session_state['_visitor_engine'],'POST','/score/batch/csv',files={'file':('test.csv',(root/'data/fraud_test_50_unique.csv').read_bytes(),'text/csv')})
assert len(rows)==50
assert len(a.session_state['_visitor_engine'].recent(100))<50
print('PASS: embedded normal/scam demos, five system checks, visitor isolation, and 50-row CSV batch.')
