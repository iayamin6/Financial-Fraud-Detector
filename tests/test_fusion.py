import pytest
from fraud.config import load_config
from fraud.fusion import fuse

def test_rule_override_is_explained_and_bounded():
    cfg=load_config(); result=fuse(dict(text=.98,behavioral=0.,network=0.,rules=.98),cfg)
    assert result['decision']=='auto_block'
    assert result['score']==pytest.approx(sum(result['contributions'].values())+result['rule_override_delta'])
    assert 0<=result['score']<=1

def test_threshold_boundaries_and_monotonicity():
    cfg=load_config()
    for score,tier in [(0,'low'),(cfg['fusion']['review_threshold'],'medium'),(cfg['fusion']['block_threshold'],'high'),(.99,'high')]:
        result=fuse(dict.fromkeys(['text','behavioral','network','rules'],score),cfg)
        assert result['tier']==tier
