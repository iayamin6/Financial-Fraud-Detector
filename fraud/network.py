from datetime import timedelta
import networkx as nx

FEATURES=['recipient_flag_rate','recipient_fan_in','sender_fan_out','shared_unrelated','rapid_forwarding','sender_fan_in']

def features(tx,history,cfg):
    cutoff=tx.timestamp-timedelta(hours=cfg['network']['window_hours'])
    past=[(p,flag) for p,flag in history.events if cutoff<=p.timestamp<tx.timestamp]
    graph=nx.DiGraph()
    for p,_ in past: graph.add_edge(p.sender_id,p.recipient_id)
    incoming=[flag for p,flag in past if p.recipient_id==tx.recipient_id]
    recipient_sources=set(graph.predecessors(tx.recipient_id)) if tx.recipient_id in graph else set()
    sender_targets=set(graph.successors(tx.sender_id)) if tx.sender_id in graph else set()
    sender_sources=set(graph.predecessors(tx.sender_id)) if tx.sender_id in graph else set()
    unrelated=set()
    if tx.relationship_group:
        for p,_ in past:
            shared=bool((tx.device_id and tx.device_id==p.device_id) or (tx.ip_address and tx.ip_address==p.ip_address))
            if shared and p.relationship_group and p.relationship_group!=tx.relationship_group and p.sender_id!=tx.sender_id:
                unrelated.add(p.sender_id)
    short=tx.timestamp-timedelta(minutes=cfg['network']['forwarding_minutes'])
    receipts=sum(p.amount for p,_ in past if p.recipient_id==tx.sender_id and p.timestamp>=short)
    return dict(recipient_flag_rate=sum(incoming)/(len(incoming)+2),recipient_fan_in=float(len(recipient_sources|{tx.sender_id})),
                sender_fan_out=float(len(sender_targets|{tx.recipient_id})),shared_unrelated=float(len(unrelated)),
                rapid_forwarding=min(1.,tx.amount/receipts) if receipts else 0.,sender_fan_in=float(len(sender_sources)))

class NetworkLayer:
    def __init__(self,cfg): self.cfg=cfg
    def score(self,f):
        fan=min(1.,f['recipient_fan_in']/self.cfg['network']['fan_threshold'])
        mule=min(1.,f['sender_fan_in']/self.cfg['network']['fan_threshold'])*f['rapid_forwarding']
        w=self.cfg['network']['component_weights']
        components={'recipient_flags':w['recipient_flags']*f['recipient_flag_rate'],
                    'shared_infrastructure':w['shared_infrastructure']*min(f['shared_unrelated']/self.cfg['network']['shared_saturation'],1),
                    'fan_in_and_forwarding':w['fan_in']*fan+w['forwarding']*mule}
        reasons=[]
        if f['shared_unrelated']: reasons.append(f"Device/IP shared with {int(f['shared_unrelated'])} unrelated accounts")
        if mule: reasons.append('Recent receipts followed by rapid forwarding')
        if f['recipient_flag_rate']>0: reasons.append('Recipient has prior rule-flagged incoming transfers (unconfirmed)')
        return dict(score=max(components.values()),features=f,components=components,reasons=reasons)
