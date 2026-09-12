import json
from pathlib import Path
import numpy as np
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix, average_precision_score

def metrics(y, scores, threshold=0.5):
    y, scores = np.asarray(y), np.asarray(scores)
    pred = scores >= threshold
    return dict(n=len(y), positives=int(y.sum()), positive_definition='1 = fraud/scam; 0 = legitimate',
                threshold=threshold, precision=float(precision_score(y, pred, zero_division=0)),
                recall=float(recall_score(y, pred, zero_division=0)), f1=float(f1_score(y, pred, zero_division=0)),
                roc_auc=float(roc_auc_score(y, scores)) if len(set(y)) > 1 else None,
                pr_auc=float(average_precision_score(y, scores)),
                confusion_matrix=confusion_matrix(y, pred, labels=[0, 1]).tolist(),
                confusion_matrix_order='rows=true [legit,fraud], columns=predicted [legit,fraud]')

def save_report(cfg, name, report):
    path = Path(cfg['paths']['reports']) / f'{name}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps({name: report}, indent=2), flush=True)
