import fraud
from datetime import datetime,timezone
from time import perf_counter
from collections import Counter
from uuid import uuid4
import json
import platform
from pathlib import Path
import httpx
import numpy as np
from fraud.config import load_config
cfg=load_config(); url=f"http://{cfg['api']['host']}:{cfg['api']['port']}"; rows=[]
texts=[None,'Send your OTP immediately to our agent.','Your balance is 240. No action required.','The manager asks for a private transfer to restore access.']
with httpx.Client(base_url=url,timeout=120) as client:
    health=client.get('/health').json(); assert health.get('status')=='ready' and 'model_version' in health
    for i in range(32):
        p=dict(transaction_id=f'bench-{uuid4().hex[:12]}',sender_id=f'bench-{i%4}',recipient_id='merchant',amount=125+i,
               timestamp=datetime.now(timezone.utc).isoformat(),account_age_days=100,text=texts[i%4])
        start=perf_counter(); r=client.post('/score',json=p); r.raise_for_status(); elapsed=(perf_counter()-start)*1000
        record=r.json(); rows.append(dict(**record['latency_ms'],http_round_trip=elapsed,route=record['layers']['text']['route']))
report=dict(n=len(rows),platform=platform.platform(),model_version=health['model_version'],
    scope='Sequential local HTTP calls, warmed models, small growing demo history; excludes model startup and explanations. Not a production load test.',
    route_counts=dict(Counter(r['route'] for r in rows)),
    latency_ms={key:dict(mean=float(np.mean([r[key] for r in rows])),p50=float(np.percentile([r[key] for r in rows],50)),p95=float(np.percentile([r[key] for r in rows],95))) for key in rows[0] if key!='route'})
(Path(cfg['paths']['reports'])/'latency_benchmark.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
