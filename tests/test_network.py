from fraud.behavior import History
from fraud.network import features,NetworkLayer
from fraud.config import load_config
from test_behavior import tx


def test_shared_device_requires_unrelated_groups_and_no_future():
    cfg=load_config(); h=History(); h.add(tx(1,0,device_id='shared',relationship_group='family'))
    current=tx(2,60,sender_id='charlie',device_id='shared',relationship_group='family')
    assert features(current,h,cfg)['shared_unrelated']==0
    current.relationship_group='other'
    assert features(current,h,cfg)['shared_unrelated']==1
    h.add(tx(3,120,sender_id='future',device_id='shared',relationship_group='third'))
    assert features(current,h,cfg)['shared_unrelated']==1


def test_mule_receipts_then_forward():
    cfg=load_config(); h=History()
    for i in range(4): h.add(tx(i,i,sender_id=f's{i}',recipient_id='mule',amount=100))
    f=features(tx(9,10,sender_id='mule',recipient_id='exit',amount=400),h,cfg)
    assert f['rapid_forwarding']==1 and f['sender_fan_in']==4
    assert NetworkLayer(cfg).score(f)['score']>.6
