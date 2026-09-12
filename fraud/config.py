from pathlib import Path
import os
import yaml

ROOT = Path(__file__).resolve().parents[1]
def load_config(path=None):
    source = Path(path or os.getenv('FRAUD_CONFIG', ROOT / 'config.yaml')).resolve()
    cfg = yaml.safe_load(source.read_text())
    for key, value in cfg['paths'].items():
        cfg['paths'][key] = str((source.parent / value).resolve())
    w = cfg['fusion']['weights']
    if set(w) != {'text', 'behavioral', 'network', 'rules'} or any(v < 0 for v in w.values()) or abs(sum(w.values()) - 1) > 1e-8:
        raise ValueError('Fusion weights must be nonnegative and sum to one')
    if not 0 <= cfg['fusion']['review_threshold'] < cfg['fusion']['block_threshold'] <= 1:
        raise ValueError('Invalid decision thresholds')
    return cfg
