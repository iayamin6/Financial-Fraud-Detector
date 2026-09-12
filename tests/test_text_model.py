from fraud.config import load_config
from fraud.text import TextLayer

def test_trained_routes_and_no_text():
    layer=TextLayer(load_config())
    assert layer.score(None)['route']=='no_text'
    original=layer.bert_probabilities
    layer.bert_probabilities=lambda _: (_ for _ in ()).throw(AssertionError('Rule route must skip transformer'))
    result=layer.score('Send your OTP immediately to the agent.')
    assert result['route']=='rule_short_circuit' and result['score']>=.95
    layer.bert_probabilities=original
    result=layer.score('Your grocery purchase was completed. Thank you.')
    assert 0<=result['score']<=1
    assert result['route'] in {'baseline','bert'}
    assert result['semantic'] is not None
