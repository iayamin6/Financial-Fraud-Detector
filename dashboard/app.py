"""Beginner-friendly analyst workspace; every result comes from the real API."""
from datetime import datetime, timezone
from html import escape
from io import StringIO
from pathlib import Path
from uuid import uuid4
import os
import httpx
import pandas as pd
import streamlit as st
from fraud.config import load_config

cfg = load_config()
EMBEDDED = os.getenv('FRAUD_EMBEDDED') == '1'
st.set_page_config(page_title='Fraud Signals · Payment safety lab', page_icon='◈', layout='wide')
st.markdown('''<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
html,body,[class*="css"],.stApp{font-family:'DM Sans',sans-serif}
.stApp{background:#f5f7fc;color:#162238}
.block-container{max-width:1400px;padding:3rem 3rem 4rem}
[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebar"]{background:#101b32;border-right:0;min-width:260px;max-width:280px}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] h3{color:#d6deef!important}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p{color:#a6b4cf!important}
[data-testid="stSidebar"] [data-testid="stRadio"] label{padding:10px 8px;border-radius:8px}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked){background:#263a62}
[data-testid="stSidebar"] [data-testid="stExpander"]{background:#18263e;border-color:#30405b}
[data-testid="stSidebar"] input{color:#15233b!important}
h1{font-size:2.35rem!important;font-weight:700!important;letter-spacing:-1px;line-height:1.2!important}
h2{font-size:1.55rem!important;letter-spacing:-.4px}h3{font-size:1.15rem!important}
p{font-size:16px;line-height:1.6}
[data-testid="stCaptionContainer"] p{font-size:14px;color:#66738b}
[data-testid="stVerticalBlockBorderWrapper"]>div{border-radius:16px!important}
[data-testid="stVerticalBlockBorderWrapper"]{background:transparent}
[data-testid="stMetric"]{background:#fff;border:1px solid #e1e7f1;border-radius:14px;padding:18px}
[data-testid="stMetricValue"]{font-size:1.9rem}
.stButton>button,.stDownloadButton>button{border-radius:10px;font-weight:600;min-height:44px}
.stButton>button[kind="primary"]{background:#425ff5;border-color:#425ff5;box-shadow:0 5px 14px #425ff522}
.stButton>button:hover{border-color:#425ff5;color:#425ff5}
.stButton>button[kind="primary"]:hover{color:#fff;background:#324ee2}
.brand{font-size:23px;font-weight:700;color:white;letter-spacing:-.6px;margin:2px 0 2px}.brand span{background:#536ffe;padding:5px 10px;border-radius:10px;margin-right:9px}
.brand-sub{color:#9cabca;font-size:14px;margin:10px 0 35px}.side-note{border-top:1px solid #30405b;margin-top:40px;padding-top:20px;color:#a7b5cf;font-size:14px;line-height:1.7}
.overline{font-size:13px;color:#596d96;font-weight:700;letter-spacing:1.6px;margin-bottom:12px}.status{display:inline-flex;gap:8px;align-items:center;background:#e7f5ed;color:#166546;padding:7px 12px;border-radius:24px;font-size:14px;font-weight:600}.status:before{content:'';width:7px;height:7px;background:#20a06a;border-radius:50%}
.intro{color:#65728a;margin-bottom:24px;max-width:680px}.stepbar{display:flex;gap:24px;color:#556580;font-size:14px;margin:16px 0 22px;flex-wrap:wrap}.stepbar b{background:#e7ecff;color:#405de6;border-radius:50%;padding:4px 9px;margin-right:7px}
.st-key-scenario_normal,.st-key-scenario_scam,.st-key-scenario_custom{background:#fff;border-radius:16px;box-shadow:0 5px 20px #15213e05}.st-key-scenario_scam{border-color:#cdd6ff!important}.demo-icon{height:46px;width:46px;display:grid;place-items:center;border-radius:13px;font-size:23px;margin:4px 0 18px;background:#ebefff;color:#425ff5}.demo-icon.danger{background:#fff0ed;color:#d34e43}.demo-icon.custom{background:#eef2f9;color:#425878}
.tag{font-size:12px;letter-spacing:.7px;font-weight:700;color:#667b9b;text-transform:uppercase}.scenario-title{font-size:21px;font-weight:700;margin:10px 0 8px;letter-spacing:-.3px}.scenario-text{color:#64728a;font-size:15px;min-height:70px;line-height:1.6}.message{background:#f3f5fa;border:1px solid #e5e9f2;border-radius:10px;padding:14px;font-size:14px;color:#40516b;line-height:1.6;min-height:103px;margin:18px 0}.expect{font-size:14px;color:#52647e;margin:12px 0}
.result{display:flex;align-items:center;gap:28px;background:white;border:1px solid #dce4f0;border-radius:18px;padding:26px;margin:10px 0 22px}.gauge{width:120px;height:120px;min-width:120px;border-radius:50%;display:grid;place-items:center}.gauge-inner{width:99px;height:99px;background:white;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-direction:column}.gauge strong{font-size:32px;line-height:1.1}.gauge small{color:#68758c;font-size:12px}.result h2{margin:0!important;padding:8px 0!important}.result p{margin:0;color:#62718b;font-size:15px}.badge{font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase}
.signal{background:white;border:1px solid #e0e7f2;padding:15px 18px;border-radius:12px;margin-bottom:10px}.signal-head{display:flex;justify-content:space-between;font-weight:600;font-size:15px}.track{height:6px;background:#edf1f8;border-radius:6px;overflow:hidden;margin:10px 0}.track>div{height:100%;background:#5871ef;border-radius:6px}.signal-note{font-size:13px;color:#72809a}.checkline{display:flex;justify-content:space-between;gap:12px;padding:13px 0;border-bottom:1px solid #e6ebf4;font-size:15px}.passed{color:#14714a;font-weight:700}.failed{color:#bd3848;font-weight:700}
@media(max-width:800px){.block-container{padding:2.5rem 1rem}h1{font-size:1.8rem!important}.result{padding:18px;gap:15px}.gauge{width:96px;height:96px;min-width:96px}.gauge-inner{width:79px;height:79px}.stepbar{gap:12px}}
@media(prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>''', unsafe_allow_html=True)

PAGES = ['Try a demo', 'Check a payment', 'Recent checks', 'Upload a CSV', 'How it works']
with st.sidebar:
    st.markdown('<div class="brand"><span>◈</span> Fraud Signals</div><div class="brand-sub">Payment safety lab</div>', unsafe_allow_html=True)
    page = st.radio('Workspace', PAGES, key='page', label_visibility='collapsed')
    st.markdown('<div class="side-note">A safe place to explore fraud detection.<br><br>All checks are recommendations. No money is moved or blocked.</div>', unsafe_allow_html=True)
    if EMBEDDED:
        st.caption('Your checks are private to this browser session. They may disappear when the session ends or the app restarts.')
    with st.expander('Connection settings'):
        url = st.text_input('Service address', value=os.getenv('FRAUD_API_URL', f"http://{cfg['api']['host']}:{cfg['api']['port']}"), key='api_url', disabled=EMBEDDED).rstrip('/')
        st.caption('Hosted mode uses the built-in scoring engine; this address is unused.' if EMBEDDED else 'You can leave this as it is when running the demo on this computer.')


def request(method, path, **kwargs):
    if EMBEDDED:
        from dashboard.embedded import dispatch, session_engine
        return dispatch(session_engine(), method, path, **kwargs)
    response = httpx.request(method, url + path, timeout=120 if method == 'POST' else 8, **kwargs)
    if response.is_error:
        try: detail = response.json().get('detail', response.text)
        except ValueError: detail = response.text
        raise RuntimeError(f'{response.status_code}: {detail}')
    return response.json()


def error_message(exc):
    if isinstance(exc, httpx.HTTPError):
        st.error('The scoring service is not responding. Your payment has not been checked. Try again when the service is available.')
    else:
        st.error('This check could not be completed. Please review the details below and try again.')
        with st.expander('See the details'): st.write(str(exc))


try:
    health = request('GET', '/health')
    policy = request('GET', '/policy')
except (httpx.HTTPError, RuntimeError) as exc:
    st.title('Let’s connect your scoring service')
    st.info('The screen is available, but the part that checks payments is offline. No result can be generated yet.')
    st.write('Open a terminal in the project folder, activate the Python environment, then run:')
    st.code('python scripts/run_api.py')
    st.button('Try connecting again')
    st.stop()

header, status = st.columns([4, 1])
header.markdown('<div class="overline">WORKSPACE / ' + escape(page.upper()) + '</div>', unsafe_allow_html=True)
status.markdown('<span class="status">System ready</span>', unsafe_allow_html=True)


def demo_payload(kind):
    return dict(transaction_id=f'guided-{kind}-{uuid4().hex[:10]}', sender_id=f'practice-{uuid4().hex[:8]}',
                recipient_id='sample-store', amount=150, timestamp=datetime.now(timezone.utc).isoformat(),
                account_age_days=365, text='Grocery purchase receipt. Thank you.' if kind == 'normal' else 'Send your OTP to the bank agent immediately to restore your account.')


def run_demo(kind):
    try:
        with st.spinner('Checking the message, payment and account connections…'):
            result = request('POST', '/score', json=demo_payload(kind))
        st.session_state['demo_result'] = result
        st.session_state['demo_kind'] = kind
    except (httpx.HTTPError, RuntimeError) as exc:
        error_message(exc)
        return False
    return True


def go_custom(): st.session_state['page'] = 'Check a payment'


def friendly_reason(reason):
    if 'prior rule-flagged' in reason: return 'This recipient has received payments with warning signs before. Those flags are unconfirmed.'
    if reason.lower() in {'send your otp', 'share your otp'}: return 'The message asks for an OTP: a secret, one-time verification code.'
    if 'scam evidence' in reason: return 'The wording resembles scam messages in the training examples.'
    if reason == 'New payee': return 'This recipient has not been paid before in the available history.'
    if reason == 'Device changed': return 'The sender is using a different device.'
    if 'rule floor' in reason: return 'A direct request for a secret code triggered a strong scam rule.'
    if 'sender median' in reason: return reason.replace('sender median', 'the sender’s typical payment')
    if 'historical rate' in reason: return reason.replace('historical rate', 'the sender’s usual rate')
    return reason


def show_result(record, key):
    tier = record['risk_tier']; score = round(record['fraud_score'] * 100)
    palette = {'low': '#16815d', 'medium': '#ba790d', 'high': '#d34855'}
    titles = {'low': 'No strong warning signs found', 'medium': 'This payment deserves a closer look', 'high': 'Strong scam warning signs detected'}
    actions = {'low': 'The demo recommends allowing this payment. A low score is not a guarantee of safety.',
               'medium': 'The demo recommends a person review this payment before proceeding.',
               'high': 'The demo recommends blocking this payment for review. No real payment has been blocked.'}
    color = palette[tier]
    st.markdown(f'''<div class="result"><div class="gauge" style="background:conic-gradient({color} {score}%,#edf1f7 0)"><div class="gauge-inner"><strong>{score}<span style="font-size:15px;color:#7b879a">/100</span></strong><small>RISK INDEX</small></div></div><div><span class="badge" style="color:{color}">{tier} risk</span><h2>{titles[tier]}</h2><p>{actions[tier]}</p></div></div>''', unsafe_allow_html=True)
    left, right = st.columns([1.15, 1])
    with left:
        st.subheader('Why this result?')
        for reason in record['reasons'][:4]: st.write('• ' + friendly_reason(reason))
        st.caption('These are observations, not proof of fraud. A new recipient alone does not make a payment unsafe.')
    with right:
        for field, title, description in [('text', 'Message clues', 'Does the wording resemble a scam?'), ('behavioral', 'Payment behavior', 'Is the amount or activity unusual?'), ('network', 'Account connections', 'Are there suspicious relationships?')]:
            value = round(record['sub_scores'][field] * 100)
            st.markdown(f'<div class="signal"><div class="signal-head"><span>{title}</span><span>{value}/100</span></div><div class="track"><div style="width:{value}%"></div></div><div class="signal-note">{description}</div></div>', unsafe_allow_html=True)
    st.caption('The risk index is a model score, not the percentage chance of fraud. This system was trained and evaluated on synthetic examples.')
    with st.expander('Explore the detailed explanation'):
        st.write('See which inputs affected the result. This can take a few seconds.')
        if st.button('Explain this result', key=f'explain_{key}'):
            try:
                with st.spinner('Preparing the explanation…'):
                    st.session_state[f'explanation_{key}'] = request('POST', f"/explain/{record['transaction_id']}")
            except (httpx.HTTPError, RuntimeError) as exc: error_message(exc)
        explanation = st.session_state.get(f'explanation_{key}')
        if explanation and explanation['transaction_id'] == record['transaction_id']:
            st.success('Explanation loaded from the saved payment check.')
            contributions = pd.DataFrame(explanation['methods']['behavioral']['contributions'])
            st.dataframe(contributions.sort_values('contribution', ascending=False), hide_index=True, width='stretch')
            st.caption('Positive contributions raise the behavioral risk score; negative contributions reduce it. These SHAP values are model attributions, not causal evidence.')
            st.json(explanation['methods']['text'], expanded=False)
        st.write('**How the final score was calculated**')
        st.dataframe(pd.DataFrame([{'Signal': k, 'Contribution': v} for k, v in record['fusion']['contributions'].items()]), hide_index=True, width='stretch')
        st.caption(f"Weighted score {record['fusion']['weighted_sum']:.3f} + strong-rule adjustment {record['fusion']['rule_override_delta']:.3f} = {record['fraud_score']:.3f}")
        st.json(record['layers']['text'], expanded=False)
    with st.expander('Was this result right? Send feedback'):
        label = st.radio('What was this payment actually?', ['Legitimate', 'Fraud'], horizontal=True, key=f'label_{key}')
        if st.button('Save my feedback', key=f'feedback_{key}'):
            try:
                request('POST', '/feedback', json={'transaction_id': record['transaction_id'], 'correct_label': int(label == 'Fraud')})
                st.success('Feedback saved. It can be used for a future model update; it does not change today’s score.')
            except (httpx.HTTPError, RuntimeError) as exc: error_message(exc)
    with st.expander('Technical details'):
        st.json(record, expanded=False)


@st.dialog('Your payment check', width='large')
def demo_dialog():
    show_result(st.session_state['demo_result'], 'demo')


if page == 'Try a demo':
    st.title('Your first fraud check. Made simple.')
    st.markdown('<div class="intro">Pick an example below. We’ll check it and explain the result—no setup, files or technical knowledge needed.</div><div class="stepbar"><span><b>1</b>Choose an example</span><span><b>2</b>Run the check</span><span><b>3</b>Understand the result</span></div>', unsafe_allow_html=True)
    a, b, c = st.columns(3)
    scenarios = [(a, 'normal', '↗', 'EVERYDAY PAYMENT', 'A normal purchase', 'A small payment with an ordinary receipt and no request for secret information.', 'Grocery purchase receipt. Thank you.', 'Expected: low risk', 'Try normal payment'),
                 (b, 'scam', '!', 'SOCIAL ENGINEERING', 'An OTP scam', 'The same payment amount, but the message asks you to reveal a secret code.', 'Send your OTP to the bank agent immediately to restore your account.', 'Expected: high risk', 'Try OTP scam')]
    for column, kind, icon, tag, title, desc, message, expected, button in scenarios:
        with column, st.container(border=True, key=f'scenario_{kind}'):
            st.markdown(f'<div class="demo-icon {"danger" if kind == "scam" else ""}">{icon}</div><div class="tag">{tag}</div><div class="scenario-title">{title}</div><div class="scenario-text">{desc}</div><div class="message">“{message}”</div><div class="expect">{expected}</div>', unsafe_allow_html=True)
            if st.button(button, key=f'demo_{kind}', width='stretch', type='primary' if kind == 'scam' else 'secondary'):
                if run_demo(kind): demo_dialog()
    with c, st.container(border=True, key='scenario_custom'):
        st.markdown('<div class="demo-icon custom">✎</div><div class="tag">YOUR TURN</div><div class="scenario-title">Test your own idea</div><div class="scenario-text">Change the amount or message and see how the system responds.</div><div class="message">Start with a sample payment.<br>Only an amount and a message are needed.</div><div class="expect">No banking connection required</div>', unsafe_allow_html=True)
        st.button('Create a payment check', on_click=go_custom, width='stretch')
    if st.session_state.get('demo_result'):
        last = st.session_state['demo_result']
        if st.button(f"View last demo result · {last['risk_tier'].title()} risk · {round(last['fraud_score'] * 100)}/100", key='last_result'): demo_dialog()
    st.divider()
    st.subheader('Want to know if everything is working?')
    st.write('Run a quick check of the connection, two sample payments, saved results and an explanation. It adds two synthetic examples to Recent checks.')
    if st.button('Run system check', key='system_check', icon=':material/fact_check:'):
        checks = []
        try:
            with st.status('Testing the system…', expanded=True) as progress:
                ready = request('GET', '/health')
                checks.append(('Scoring service responds', ready.get('status') == 'ready'))
                st.write('Checking a normal payment…')
                normal = request('POST', '/score', json=demo_payload('normal'))
                checks.append(('Normal example returns low risk', normal['risk_tier'] == 'low'))
                st.write('Checking an OTP scam…')
                scam = request('POST', '/score', json=demo_payload('scam'))
                checks.append(('OTP example returns high risk', scam['risk_tier'] == 'high'))
                recent = request('GET', '/transactions?limit=100')
                ids = {r['transaction_id'] for r in recent}
                checks.append(('Both checks were saved', normal['transaction_id'] in ids and scam['transaction_id'] in ids))
                st.write('Retrieving an explanation…')
                explanation = request('POST', f"/explain/{scam['transaction_id']}")
                checks.append(('Detailed explanation is available', explanation['transaction_id'] == scam['transaction_id'] and explanation['methods']['behavioral']['reconstruction_error'] < 1e-6))
                progress.update(label='System check complete', state='complete' if all(v for _, v in checks) else 'error', expanded=False)
        except (httpx.HTTPError, RuntimeError, KeyError) as exc:
            checks.append(('Complete end-to-end check', False)); error_message(exc)
        st.session_state['system_checks'] = checks
    if 'system_checks' in st.session_state:
        checks = st.session_state['system_checks']
        for label, passed in checks:
            st.markdown(f'<div class="checkline"><span>{escape(label)}</span><span class="{"passed" if passed else "failed"}">{"✓ Passed" if passed else "Needs attention"}</span></div>', unsafe_allow_html=True)
        if all(v for _, v in checks): st.success('All 5 checks passed. The app can score, save and explain these examples.')
        else: st.warning('At least one check needs attention. The actual results are shown above; a failed expectation is not hidden.')
        st.caption('This verifies the app’s functionality on simple examples. It does not prove it will catch every real scam.')

elif page == 'Check a payment':
    st.title('What would you like to check?')
    st.write('Try a payment amount and its associated message. Use sample details and avoid entering real account numbers or secret codes.')
    with st.form('payment_form'):
        amount = st.number_input('Payment amount', min_value=.01, value=150., step=50., help='Use the same currency for all examples. No currency conversion is performed.')
        text = st.text_area('Message or payment note', value='Grocery purchase receipt. Thank you.', height=120, help='Paste the wording of an SMS, chat or payment note. This can also be left empty.')
        with st.expander('Optional: account and device details'):
            st.caption('Reusing a sender lets the system compare with that sender’s earlier payments.')
            a, b = st.columns(2)
            sender = a.text_input('Sender name or sample ID', 'my-demo-account')
            recipient = b.text_input('Recipient name or sample ID', 'sample-store')
            age = a.number_input('Account age in days', min_value=0, value=365)
            device = b.text_input('Device name', 'my-demo-phone')
        submitted = st.form_submit_button('Check this payment', type='primary', width='stretch')
    if submitted:
        st.session_state.pop('custom_result', None)
        try:
            payload = dict(transaction_id=f'check-{uuid4().hex[:12]}', sender_id=sender, recipient_id=recipient, amount=amount,
                           timestamp=datetime.now(timezone.utc).isoformat(), account_age_days=age, device_id=device or None, text=text or None)
            with st.spinner('Looking for warning signs…'): st.session_state['custom_result'] = request('POST', '/score', json=payload)
        except (httpx.HTTPError, RuntimeError) as exc: error_message(exc)
    if st.session_state.get('custom_result'): show_result(st.session_state['custom_result'], 'custom')

elif page == 'Recent checks':
    st.title('Every check, with a clear explanation.')
    st.caption('Browse saved results. Demo and system-check examples appear here too.')
    try:
        rows = request('GET', '/transactions?limit=500'); metrics = request('GET', '/metrics')
    except (httpx.HTTPError, RuntimeError) as exc: error_message(exc); st.stop()
    cols = st.columns(4)
    cols[0].metric('Total checks', metrics['scored_transactions'])
    cols[1].metric('Low risk · recent', sum(r['risk_tier'] == 'low' for r in rows))
    cols[2].metric('Need review · recent', sum(r['risk_tier'] == 'medium' for r in rows))
    cols[3].metric('High risk · recent', sum(r['risk_tier'] == 'high' for r in rows))
    filter_tier = st.pills('Show', ['All', 'Low risk', 'Needs review', 'High risk'], default='All')
    filtered = [r for r in rows if filter_tier in (None, 'All') or r['risk_tier'] == {'Low risk': 'low', 'Needs review': 'medium', 'High risk': 'high'}[filter_tier]]
    with st.expander('Advanced: preview different decision thresholds'):
        st.caption('These sliders change only the preview labels. They do not change saved results or the scoring service.')
        review = st.slider('Review at', 0.05, .94, float(policy['review_threshold']), .005, key='review_slider')
        block = st.slider('Block at', .06, 1., float(policy['block_threshold']), .005, key='block_slider')
        if review >= block: st.warning('Review must be below block. The preview will use the saved thresholds.'); review, block = policy['review_threshold'], policy['block_threshold']
        st.caption(f"Mean scoring time: {metrics['average_latency_ms']['total_pipeline']:.1f} ms, excluding storage, HTTP and explanations.")
    if filtered:
        table = pd.DataFrame([{'Check': r['transaction_id'], 'Risk / 100': round(r['fraud_score'] * 100), 'Saved result': r['risk_tier'].title(),
                               'Preview': 'High' if r['fraud_score'] >= block else 'Medium' if r['fraud_score'] >= review else 'Low'} for r in filtered])
        colors = {'Low': '#e5f5ed', 'Medium': '#fff1d7', 'High': '#ffeaec'}
        st.dataframe(table.style.map(lambda v: f'background-color:{colors[v]};color:#17243c', subset=['Saved result', 'Preview']), hide_index=True, width='stretch')
        selected = st.selectbox('Choose a check to see why', [r['transaction_id'] for r in filtered], key='inspection')
        show_result(next(r for r in filtered if r['transaction_id'] == selected), 'history')
    else: st.info('No checks match this view. Try another filter or run an example from Try a demo.')

elif page == 'Upload a CSV':
    st.title('Check several payments at once.')
    st.write('Use this when you have a table of payments. For your first test, download the sample and upload that same file below.')
    sample = pd.DataFrame([demo_payload('normal'), demo_payload('scam')]).to_csv(index=False)
    st.download_button('1. Download a ready-to-test CSV', sample, file_name='sample-payments.csv', mime='text/csv', key='download_csv')
    upload = st.file_uploader('2. Upload your CSV', type=['csv'])
    fresh = st.checkbox('Treat these as new demo payments', value=True, help='Creates new sample IDs and current timestamps in a copy before scoring. This avoids conflicts with older checks. Turn off to preserve original IDs and dates.')
    st.caption('Demo mode keeps the payment details and row order, but gives every row a new ID and current time. Your original file is unchanged.')
    if st.button('3. Check uploaded payments', disabled=upload is None, type='primary'):
        st.session_state.pop('batch_results', None)
        try:
            raw = upload.getvalue()
            if len(raw) > cfg['api']['csv_max_bytes']: raise RuntimeError('The file is too large. Use a file smaller than 2 MB.')
            if fresh:
                import csv
                from datetime import timedelta
                reader = csv.DictReader(StringIO(raw.decode('utf-8-sig')))
                if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)): raise RuntimeError('Your CSV needs unique column names.')
                data = list(reader)
                if not 1 <= len(data) <= cfg['api']['batch_limit']: raise RuntimeError('Please use between 1 and 250 rows.')
                now = datetime.now(timezone.utc)
                for i, row in enumerate(data):
                    row['transaction_id'] = f'upload-{uuid4().hex[:12]}'
                    row['timestamp'] = (now + timedelta(microseconds=i)).isoformat()
                raw = pd.DataFrame(data).to_csv(index=False).encode()
            with st.spinner('Checking your payments…'):
                results = request('POST', '/score/batch/csv', files={'file': (upload.name, raw, 'text/csv')})
            st.session_state['batch_results'] = results
        except (httpx.HTTPError, RuntimeError, ValueError, UnicodeError) as exc: error_message(exc)
    if 'batch_results' in st.session_state:
        results = st.session_state['batch_results']; st.success(f'{len(results)} payments checked and saved. Find the full explanations in Recent checks.')
        st.dataframe(pd.DataFrame([{'Check': r['transaction_id'], 'Risk / 100': round(r['fraud_score'] * 100), 'Result': r['risk_tier']} for r in results]), hide_index=True, width='stretch')
    with st.expander('Preparing your own file'):
        st.write('Required columns: transaction_id, sender_id, recipient_id, amount, timestamp, account_age_days. Optional: text, device_id, ip_address, relationship_group, country.')
        st.write('Keep amounts positive. Use timestamps with a UTC offset. Do not include training labels or scenario columns. Limit: 250 payments / 2 MB.')
        st.write('With demo mode off, historical payments older than the last saved check are rejected. Repeating the same ID and identical details returns its saved result.')

else:
    st.title('A simple guide to what you’re seeing.')
    st.subheader('Start here: a 30-second walkthrough')
    st.write('1. Open **Try a demo** and click **Try normal payment**. Expect a low-risk result.')
    st.write('2. Click **Try OTP scam**. The amount is the same, but the request for a secret code should produce high risk.')
    st.write('3. Read **Why this result?** Then try **Run system check**. Five green checks mean scoring, saving and explaining worked on those examples.')
    st.divider()
    a, b, c = st.columns(3)
    for col, title, desc in [(a, 'Low risk', 'No strong warning signs. The demo recommends allowing the payment, but this is not a safety guarantee.'),
                              (b, 'Needs review', 'Something is unusual. A person should investigate before deciding.'),
                              (c, 'High risk', 'Strong warning signs. The demo recommends blocking for review; it does not move or block real money.')]:
        with col, st.container(border=True): st.subheader(title); st.write(desc)
    st.subheader('What does the system look at?')
    st.write('**The message:** requests for secret codes, pressure tactics and wording similar to known scams.')
    st.write('**The payment:** an unusual amount, a new recipient, repeated activity or a changed device.')
    st.write('**Account connections:** patterns between accounts, such as rapid forwarding or shared devices.')
    st.write('**Known rules:** a direct request to share an OTP can trigger a high-risk result even when the amount seems normal.')
    with st.expander('What is an OTP? What does 90/100 mean?'):
        st.write('An OTP is a one-time password or verification code. A request to tell someone that secret code is a warning sign. “Never share your OTP” is a safety advisory, which the rules handle differently.')
        st.write('90/100 is a risk index, not a 90% probability of fraud. The number combines several signals.')
    with st.expander('Does a passing system check mean it catches every scam?'):
        st.write('No. It proves these app functions worked on the included examples. The model was trained on synthetic data and can miss scams or flag legitimate payments. It needs independent evaluation before real banking use.')
    with st.expander('How can a developer run the automated tests?'):
        st.code('python -m pytest -q')
        st.write('Run this from the project folder with the Python environment activated. These tests check rules, transaction history, input validation, API responses and persistence. The browser system check is the easier starting point.')
