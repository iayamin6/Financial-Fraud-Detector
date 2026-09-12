"""Transparent risk index. A v2 meta-model can replace this interface."""
import math
def fuse(sub_scores,cfg):
    contributions={k:float(cfg['fusion']['weights'][k]*v) for k,v in sub_scores.items()}
    raw=round(math.fsum(contributions.values()),12)
    floor=cfg['fusion']['hard_rule_floor'] if sub_scores['rules']>=cfg['nlp']['rule_short_circuit'] else 0.
    score=max(raw,floor)
    if score>=cfg['fusion']['block_threshold']: tier,decision='high','auto_block'
    elif score>=cfg['fusion']['review_threshold']: tier,decision='medium','manual_review'
    else: tier,decision='low','auto_pass'
    return dict(score=score,tier=tier,decision=decision,contributions=contributions,
                weighted_sum=raw,rule_override_delta=score-raw,
                thresholds={k:cfg['fusion'][k] for k in ['review_threshold','block_threshold']},
                missing_text_policy='Fixed weights; missing text contributes zero, without asserting the transaction is safe.')
