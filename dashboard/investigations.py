"""Analyst workspace layered onto the original Streamlit navigation."""
import json
import streamlit as st
import pandas as pd


def cases_page(request):
    st.title('FraudShield · Investigation workspace')
    st.caption('AML and model alerts are unconfirmed indicators. Only a human analyst records the outcome.')
    with st.expander('Try an AML investigation',expanded=True):
        scenario=st.selectbox('Synthetic pattern',['Structuring','Rapid forwarding','Circular transfers'])
        if st.button('Load AML example',key='aml_demo'):
            from fraud.demo import aml_example
            from fraud.config import load_config
            request('POST','/score/batch',json=aml_example(scenario,load_config()));st.rerun()
    with st.expander('Create a case for an existing payment'):
        txid=st.text_input('Transaction ID',key='case_txid')
        if st.button('Create case',key='create_case'):
            request('POST','/cases',json={'transaction_id':txid});st.rerun()
    cases=request('GET','/cases')
    if not cases:
        st.info('Run the OTP demo or upload payments first. Review-worthy payments automatically create a case.');return
    st.dataframe(pd.DataFrame(cases),hide_index=True,width='stretch')
    cid=st.selectbox('Select a case',[c['case_id'] for c in cases],format_func=lambda x:next(f"{c['transaction_id']} · {c['status']}" for c in cases if c['case_id']==x),key='selected_case')
    case=request('GET','/cases/'+cid);score=case['score']; b=score['layers']['behavioral']
    a,c,d=st.columns(3)
    a.metric('Fused risk',f"{score['fraud_score']*100:.0f}/100")
    c.metric('Supervised model',f"{b['xgboost']*100:.0f}/100")
    d.metric('Anomaly score',f"{b['isolation']*100:.0f}/100")
    st.caption('These scores are uncalibrated; unusual activity alone is not fraud.')
    st.write('**Reasons:**',score['reasons'])
    aml=score['layers'].get('aml',{})
    for alert in aml.get('alerts',[]): st.warning(f"{alert['kind']}: {alert['detail']}")
    if not aml.get('alerts'): st.info('No saved AML indicators for this payment.')
    with st.expander('Transaction and saved model evidence'):
        st.json(case['transaction']);st.json(score)
    with st.expander('Account and device relationships'):
        graph=aml.get('relationships',{'nodes':[],'edges':[]})
        if graph['nodes']:
            # JSON encoding protects quoted labels/identifiers from DOT injection.
            lines=['digraph relationships { rankdir=LR;']
            for n in graph['nodes']:
                lines.append(f'{json.dumps(n["id"])} [label={json.dumps(n["label"])}, shape={"box" if n["kind"]=="transaction" else "ellipse"}];')
            for e in graph['edges']: lines.append(f'{json.dumps(e["source"])} -> {json.dumps(e["target"])} [label={json.dumps(e["relation"])}];')
            lines.append('}');st.graphviz_chart('\n'.join(lines))
            st.dataframe(pd.DataFrame(graph['edges']),hide_index=True)
            if graph.get('truncated'): st.caption('Bounded neighborhood shown; additional relationships omitted.')
        else: st.write('No saved graph evidence for this legacy payment.')
    with st.expander('SHAP / LIME explanation'):
        if st.button('Load original model explanation',key='case_explain'):
            st.json(request('POST','/explain/'+case['transaction_id']))
    if case['status']!='resolved':
        with st.form('case_edit'):
            assignee=st.text_input('Assigned analyst',value=case['assigned_to'] or '')
            note=st.text_area('Investigation note (no passwords or secret codes)')
            status=st.selectbox('Status',['open','under_review'] if case['status']=='open' else ['under_review'])
            if st.form_submit_button('Save case update'):
                body={'revision':case['revision'],'status':status,'assigned_to':assignee}
                if note.strip(): body['note']=note
                request('PATCH','/cases/'+cid,json=body);st.rerun()
        if st.button('Run investigation workflow',key='investigate'):
            with st.spinner('Collecting evidence and retrieving guidance…'): request('POST','/cases/'+cid+'/investigate')
            st.rerun()
    for run in case['investigations']:
        with st.expander(f"Investigation · {run['status']}",expanded=True):
            detail=request('GET','/investigations/'+run['run_id'])
            report=(detail.get('result') or {}).get('report')
            if report:
                st.json(report)
                st.download_button('Download investigation report',json.dumps(report,indent=2),file_name=run['run_id']+'.json',mime='application/json',key='download_'+run['run_id'])
            if detail['error']: st.error(detail['error'])
            if run['status'] in {'failed','running'}:
                if st.button('Resume interrupted workflow',key='retry_'+run['run_id']):
                    request('POST','/investigations/'+run['run_id']+'/retry');st.rerun()
            if run['status']=='awaiting_review' and case['status']!='resolved':
                with st.form('review_'+run['run_id']):
                    outcome=st.selectbox('Analyst outcome',['inconclusive','legitimate','confirmed_fraud'])
                    rationale=st.text_area('Required rationale')
                    st.caption('This records your human decision. It does not retrain models or block money.')
                    if st.form_submit_button('Record outcome and resolve case'):
                        request('POST','/investigations/'+run['run_id']+'/resume',json={'outcome':outcome,'note':rationale,'revision':case['revision']});st.rerun()
    with st.form('case_question'):
        question=st.text_input('Ask the investigation guide',value='Which guidelines apply to requests to share an OTP?')
        if st.form_submit_button('Retrieve cited guidance'):
            with st.spinner('Searching synthetic policies…'):
                answer=request('POST','/cases/'+cid+'/ask',json={'question':question})
            st.write(answer['answer']);st.caption('Answer mode: '+answer['mode'])
            st.json(answer['citations'])
    with st.expander('Audit history'):
        st.dataframe(pd.DataFrame(case['history']),hide_index=True)


def monitoring_page(request):
    st.title('Model monitoring')
    report=request('GET','/monitoring')
    st.caption(report['limitations'])
    st.metric('Recent scored payments',report['sample_count'])
    st.write('Reference:',report['reference'])
    if report['status']=='insufficient_samples': st.info(f"At least {report['minimum_samples']} scored payments are required for distribution monitoring.")
    else: st.dataframe(pd.DataFrame(report['feature_drift']).T,width='stretch')
    st.write('Risk score PSI against synthetic validation:',report['prediction_psi_against_synthetic_validation'])
    st.subheader('Decision distribution');st.bar_chart(report['prediction_distribution'])
    st.subheader('Analyst-adjudicated outcomes')
    if report['verified_outcome_metrics']: st.json(report['verified_outcome_metrics'])
    else: st.write('Resolve cases with a confirmed fraud or legitimate outcome to evaluate adjudicated cases. Inconclusive outcomes are excluded.')
    st.caption('Model version: '+report['model_version'])
