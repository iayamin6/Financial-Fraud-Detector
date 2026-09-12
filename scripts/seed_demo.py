import fraud
from datetime import datetime,timedelta,timezone
from pathlib import Path
import csv
import json
import httpx
from fraud.config import load_config
cfg=load_config(); now=datetime.now(timezone.utc); rows=[]
for i in range(24):
    rows.append(dict(transaction_id=f'demo-seed-{i:02}',sender_id=f'customer-{i%4}',recipient_id=f'merchant-{i%3}',
                     amount=100+i*7,timestamp=(now-timedelta(minutes=60-i)).isoformat(),account_age_days=600,
                     device_id=f'device-{i%4}',relationship_group=f'group-{i%4}',text='Grocery purchase receipt. Thank you.'))
rows += [dict(transaction_id='demo-seed-scam',sender_id='customer-1',recipient_id='new-agent',amount=500,
               timestamp=(now-timedelta(minutes=2)).isoformat(),account_age_days=600,device_id='device-1',relationship_group='group-1',
               text='Send your OTP to the bank agent immediately to restore your account.'),
         dict(transaction_id='demo-seed-anomaly',sender_id='customer-2',recipient_id='new-payee',amount=9500,
               timestamp=(now-timedelta(minutes=1)).isoformat(),account_age_days=3,device_id='new-device',relationship_group='group-2',text='Payment')]
path=Path(cfg['paths']['data'])/'demo.csv'
if path.exists():
    with path.open() as f: rows=list(csv.DictReader(f))
else:
    with path.open('w') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
url=f"http://{cfg['api']['host']}:{cfg['api']['port']}"
health=httpx.get(url+'/health').json()
assert health.get('status')=='ready' and 'model_version' in health, 'Unexpected service on configured port'
r=httpx.post(url+'/score/batch',json=rows,timeout=120);r.raise_for_status()
(Path(cfg['paths']['reports'])/'demo_scores.json').write_text(json.dumps(r.json(),indent=2))
print(f'Scored {len(rows)} demo transactions. Re-running this seed reuses the saved CSV and is idempotent.')
