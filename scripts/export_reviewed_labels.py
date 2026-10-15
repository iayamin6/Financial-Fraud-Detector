"""Export reviewed labels only; training and promotion remain separate explicit steps."""
import argparse
import json
from pathlib import Path
from fraud.config import load_config
from fraud.store import Store
p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
with Store(load_config()['paths']['database']).connect() as db:
    rows=db.execute("SELECT c.case_id,c.transaction_id,c.outcome,c.updated_at,s.result_json FROM cases c JOIN scores s USING(transaction_id) WHERE c.status='resolved' AND c.outcome IN ('confirmed_fraud','legitimate')").fetchall()
records=[{'case_id':r['case_id'],'transaction_id':r['transaction_id'],'label':int(r['outcome']=='confirmed_fraud'),
          'model_version':json.loads(r['result_json'])['model_version'],'reviewed_at':r['updated_at']} for r in rows]
Path(args.output).write_text(json.dumps(records,indent=2));print(f'Exported {len(records)} adjudications; no models retrained.')
