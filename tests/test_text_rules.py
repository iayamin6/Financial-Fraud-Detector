from fraud.config import load_config
from fraud.text import rule_signals,script_signal

def test_credential_request_and_safety_advice():
    cfg=load_config()
    assert rule_signals('Send your OTP immediately.',cfg)[0][0]['name']=='credential_request'
    assert rule_signals('Never share your OTP. Do not provide your PIN.',cfg)[0]==[]
    assert rule_signals('Never share your OTP. Send your PIN to this agent.',cfg)[0]

def test_scripts_configurable():
    cfg=load_config()
    assert script_signal('hello привет',cfg)['unusual_mix']
    cfg['nlp']['allowed_script_pairs']=[['LATIN','CYRILLIC']]
    assert not script_signal('hello привет',cfg)['unusual_mix']
