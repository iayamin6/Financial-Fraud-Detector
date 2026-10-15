"""Deterministic AML indicators. Thresholds are simulation policy, not legal limits."""
from datetime import timedelta
import networkx as nx


def analyze(tx, history, cfg):
    c = cfg['aml']
    past = [p for p, _ in history.events if tx.timestamp-timedelta(minutes=c['window_minutes']) <= p.timestamp < tx.timestamp]
    outgoing = [p for p in past if p.sender_id == tx.sender_id] + [tx]
    alerts = []
    def alert(kind, detail, events):
        alerts.append({'kind': kind, 'detail': detail, 'transaction_ids': sorted({p.transaction_id for p in events}),
                       'status': 'unconfirmed', 'policy': 'synthetic monitoring policy; not a regulatory threshold'})
    if len(outgoing) >= c['velocity_count']:
        alert('velocity', f"{len(outgoing)} outgoing transfers within {c['window_minutes']} minutes", outgoing)
    threshold = c['structuring_threshold']
    near = [p for p in outgoing if threshold*c['structuring_min_fraction'] <= p.amount < threshold]
    if len(near) >= c['structuring_count'] and sum(p.amount for p in near) >= threshold:
        alert('structuring', f'{len(near)} near-threshold transfers totaling {sum(p.amount for p in near):.2f}; intent unknown', near)
    incoming = [p for p in past if p.recipient_id == tx.sender_id and p.timestamp >= tx.timestamp-timedelta(minutes=c['rapid_minutes'])]
    received = sum(p.amount for p in incoming)
    if received and tx.amount / received >= c['forwarding_ratio']:
        alert('rapid_movement', f'Outgoing amount / recent receipts = {tx.amount/received:.2f}; not proof of common funds', incoming+[tx])
        if len({p.sender_id for p in incoming}) >= c['mule_sources']:
            alert('mule_indicator', 'Multiple source accounts followed by rapid onward transfer', incoming+[tx])
    graph = nx.DiGraph()
    for p in past:
        graph.add_edge(p.sender_id, p.recipient_id)
    path = None
    if tx.sender_id != tx.recipient_id and tx.recipient_id in graph and tx.sender_id in graph:
        lengths = nx.single_source_shortest_path(graph, tx.recipient_id, cutoff=c['max_cycle_hops']-1)
        path = lengths.get(tx.sender_id)
    if path:
        edges = set(zip(path, path[1:]))
        related = [p for p in past if (p.sender_id, p.recipient_id) in edges]
        alert('circular_transfer', 'Transfer closes account path: '+' → '.join(path+[tx.recipient_id]), related+[tx])
    # UI evidence is bounded and typed. IDs are data, never executable graph markup.
    related = [p for p in past if {p.sender_id,p.recipient_id} & {tx.sender_id,tx.recipient_id} or (tx.device_id and p.device_id==tx.device_id)]
    events = (related+[tx])[-c['max_graph_edges']:]
    nodes, edges = {}, []
    for p in events:
        for account in [p.sender_id,p.recipient_id]: nodes['account:'+account]={'id':'account:'+account,'kind':'account','label':account}
        tid='transaction:'+p.transaction_id
        nodes[tid]={'id':tid,'kind':'transaction','label':p.transaction_id}
        edges.extend([{'source':'account:'+p.sender_id,'target':tid,'relation':'sent'},
                      {'source':tid,'target':'account:'+p.recipient_id,'relation':'received'}])
        if p.device_id:
            did='device:'+p.device_id; nodes[did]={'id':did,'kind':'device','label':p.device_id}
            edges.append({'source':'account:'+p.sender_id,'target':did,'relation':'used_device'})
    return {'alerts':alerts, 'requires_review':bool(alerts), 'cycle_path':path,
            'relationships':{'nodes':list(nodes.values()),'edges':edges,'truncated':len(related)+1>len(events)},
            'note':'Investigative indicators only; no finding of money laundering or automatic regulatory reporting.'}
