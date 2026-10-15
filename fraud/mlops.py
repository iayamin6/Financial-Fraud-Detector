"""Explicit local MLflow tracking, immutable fingerprints and reviewed-label exports."""
import hashlib
import json
import os
from pathlib import Path


def fingerprint(path):
    h=hashlib.sha256()
    paths=sorted(path.rglob('*')) if path.is_dir() else [path]
    for p in paths:
        if p.is_file() and '.cache' not in p.parts:
            h.update(str(p.relative_to(path) if path.is_dir() else p.name).encode())
            with p.open('rb') as f:
                for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def manifest(cfg):
    root=Path(cfg['paths']['models'])
    return {name:{'sha256':fingerprint(root/path),'artifact':path} for name,path in {
        'nlp':'bert','baseline':'text_baseline.joblib','transaction_and_anomaly':'behavior.joblib','embeddings':'embeddings','generator':'generator'}.items() if (root/path).exists()}


def flatten(obj,prefix=''):
    result={}
    for k,v in obj.items():
        key=(prefix+'.'+k).strip('.')
        if isinstance(v,dict):result.update(flatten(v,key))
        elif isinstance(v,(int,float)) and not isinstance(v,bool):result[key]=float(v)
    return result


def track(cfg,name,report):
    if not cfg.get('mlops',{}).get('enabled'):return None
    import mlflow
    # Opt in only. A remote URI must be deliberately configured by the operator.
    uri=os.getenv('MLFLOW_TRACKING_URI',(Path(cfg['paths']['reports'])/'mlruns').as_uri())
    os.environ.setdefault('MLFLOW_ALLOW_FILE_STORE','true')
    mlflow.set_tracking_uri(uri);mlflow.set_experiment(cfg['mlops']['experiment'])
    with mlflow.start_run(run_name=name) as run:
        mlflow.log_params({'seed':cfg['seed'],'behavior':json.dumps(cfg['behavior']),'nlp':json.dumps({k:v for k,v in cfg['nlp'].items() if k!='known_scams'}),
                           'evaluation_scope':'synthetic development holdout; not bank performance'})
        mlflow.log_metrics(flatten(report))
        mlflow.log_dict(report,'evaluation.json');mlflow.log_dict(manifest(cfg),'model_versions.json')
        mlflow.log_dict(cfg,'configuration.json')
        # Relevant model artifacts, including supervised and anomaly components.
        if name.startswith('text'):
            mlflow.log_artifacts(str(Path(cfg['paths']['models'])/'bert'),artifact_path='models/bert')
            mlflow.log_artifact(str(Path(cfg['paths']['models'])/'text_baseline.joblib'),artifact_path='models')
        elif name.startswith('behavior'):
            mlflow.log_artifact(str(Path(cfg['paths']['models'])/'behavior.joblib'),artifact_path='models')
        return run.info.run_id
