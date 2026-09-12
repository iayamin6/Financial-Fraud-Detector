from datetime import datetime,timedelta,timezone
from fraud.schemas import Transaction
from fraud.behavior import History,features
from fraud.config import load_config


def tx(i,minutes,**kwargs):
    values=dict(transaction_id=f't{i}',sender_id='alice',recipient_id='bob',amount=100,
                timestamp=datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=minutes),account_age_days=100)
    values.update(kwargs)
    return Transaction(**values)

def test_features_do_not_use_future_or_current_events():
    cfg=load_config(); history=History(); current=tx(2,60)
    before=features(current,history,cfg)
    history.add(tx(3,120,amount=90000)); history.add(current)
    assert features(current,history,cfg)==before

def test_prior_payee_and_window_boundary():
    cfg=load_config(); history=History(); history.add(tx(1,0))
    f=features(tx(2,60,amount=300),history,cfg)
    assert f['new_payee']==0 and f['amount_ratio']==3
    assert f['velocity_count_ratio']==2
    assert features(tx(3,61),history,cfg)['velocity_count_ratio']==1
