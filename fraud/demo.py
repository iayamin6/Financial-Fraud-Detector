"""Fresh synthetic AML event sequences for the existing batch scoring endpoint."""
from datetime import datetime,timedelta,timezone
from uuid import uuid4


def aml_example(kind,cfg):
    prefix='aml-'+uuid4().hex[:12];start=datetime.now(timezone.utc);events=[]
    def add(sender,recipient,amount):
        i=len(events)
        events.append({'transaction_id':f'{prefix}-{i}','sender_id':prefix+'-'+sender,'recipient_id':prefix+'-'+recipient,
                       'amount':amount,'timestamp':(start+timedelta(microseconds=i)).isoformat(),'account_age_days':30,
                       'text':'Synthetic AML demonstration payment','device_id':prefix+'-device-'+sender})
    if kind=='Structuring':
        for i in range(cfg['aml']['structuring_count']):add('sender','recipient'+str(i),cfg['aml']['structuring_threshold']*.9)
    elif kind=='Rapid forwarding':
        for i in range(cfg['aml']['mule_sources']):add('source'+str(i),'intermediary',100)
        add('intermediary','destination',cfg['aml']['mule_sources']*100*.95)
    elif kind=='Circular transfers':
        add('a','b',200);add('b','c',190);add('c','a',180)
    else:raise ValueError('Unknown synthetic scenario')
    return events
