"""Import saved evaluation and model artifacts into an explicit MLflow experiment."""
import json
from pathlib import Path
from fraud.config import load_config
from fraud.mlops import track, manifest
cfg=load_config();cfg['mlops']['enabled']=True
runs={}
for name in ['text_bert','behavior','network','fusion','upgrade_evaluation']:
    path=Path(cfg['paths']['reports'])/(name+'.json')
    if path.exists(): runs[name]=track(cfg,name,json.loads(path.read_text()))
(Path(cfg['paths']['reports'])/'model_versions.json').write_text(json.dumps(manifest(cfg),indent=2))
print(json.dumps({'runs':runs,'note':'Historical reports imported as evaluation runs, not newly retrained models.'},indent=2))
