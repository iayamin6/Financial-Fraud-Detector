"""Live beginner-flow checks; requires the API, and adds synthetic examples."""
from streamlit.testing.v1 import AppTest
from pathlib import Path
import json
at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'dashboard'/'app.py'),default_timeout=60).run()
assert not at.exception, at.exception
at.button(key='demo_normal').click().run()
assert not at.exception, at.exception
assert at.session_state['demo_result']['risk_tier']=='low'
at.button(key='demo_scam').click().run()
assert not at.exception, at.exception
assert at.session_state['demo_result']['risk_tier']=='high'
at.button(key='system_check').click().run(timeout=120)
assert not at.exception, at.exception
assert len(at.session_state['system_checks'])==5
assert all(passed for _,passed in at.session_state['system_checks'])
at.radio(key='page').set_value('Check a payment').run()
assert not at.exception, at.exception
at.button(key='FormSubmitter:payment_form-Check this payment').click().run()
assert not at.exception, at.exception
assert 'custom_result' in at.session_state
at.radio(key='page').set_value('Recent checks').run()
assert not at.exception, at.exception
at.slider(key='review_slider').set_value(.45).run()
assert not at.exception, at.exception
at.radio(key='page').set_value('Upload a CSV').run()
assert not at.exception, at.exception
at.radio(key='page').set_value('How it works').run()
assert not at.exception, at.exception
Path('reports/dashboard_qa.json').write_text(json.dumps({'passed':['normal demo is low risk','OTP scam demo is high risk','all 5 system checks pass','custom form scores payment','recent checks and threshold preview render','CSV page renders','beginner guide renders'],'method':'Streamlit AppTest against live API'},indent=2))
print('PASS: guided demos, all five system checks, custom payment form, history, CSV page, and beginner guide.')
