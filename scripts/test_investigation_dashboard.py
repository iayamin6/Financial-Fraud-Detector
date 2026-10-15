from pathlib import Path
from streamlit.testing.v1 import AppTest
root=Path(__file__).resolve().parents[1]
at=AppTest.from_file(str(root/'streamlit_app.py'),default_timeout=120).run()
assert not at.exception,at.exception
at.button(key='demo_scam').click().run()
assert not at.exception,at.exception
at.radio(key='page').set_value('Investigations').run()
assert not at.exception,at.exception
assert len(at.selectbox(key='selected_case').options)==1
at.button(key='investigate').click().run(timeout=120)
assert not at.exception,at.exception
assert not at.error,[e.value for e in at.error]
engine=at.session_state['_visitor_engine']
from fraud.cases import Cases
from fraud.workflows import Investigations
case=Cases(engine).get(Cases(engine).list()[0]['case_id'])
assert case['investigations'][0]['status']=='awaiting_review',case['investigations']
review_form='review_'+case['investigations'][0]['run_id']
# Exercise the actual human review form.
next(x for x in at.text_area if x.label=='Required rationale').set_value('Synthetic OTP example reviewed by analyst')
at.button(key='FormSubmitter:'+review_form+'-Record outcome and resolve case').click().run()
assert not at.exception,at.exception
assert Cases(engine).get(case['case_id'])['status']=='resolved'
# Loading another example must not keep actions bound to the previous case.
at.button(key='aml_demo').click().run()
assert not at.exception,at.exception
selected=at.selectbox(key='selected_case').value
assert selected != case['case_id']
new_case=Cases(engine).get(selected)
assert new_case['score']['layers']['aml']['requires_review']
at.run()
assert at.selectbox(key='selected_case').value == selected
at.radio(key='page').set_value('Model monitoring').run()
assert not at.exception,at.exception
print('PASS: cloud case creation, graph UI, real LangGraph + local LLM, human review, audit and monitoring.')
