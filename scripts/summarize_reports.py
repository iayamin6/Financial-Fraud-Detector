import fraud
import json
from pathlib import Path
from fraud.config import load_config
cfg=load_config(); root=Path(cfg['paths']['reports'])
def get(name): return json.loads((root/f'{name}.json').read_text())
entries=[('TF-IDF baseline',get('text_baseline')),('DistilBERT',get('text_bert')['binary']),('Full text layer',get('text_layer')),
         ('Behavioral ensemble',get('behavior')['test']),('Network formula',get('network')['network_test']),
         ('XGBoost + graph (ablation)',get('network')['ablation_after_behavior_plus_graph_xgb']),
         ('Fusion: review or block',get('fusion')['test']),('Fusion: block only',get('fusion')['test_auto_block'])]
lines=['# Evaluation results','', 'All data are original synthetic scenarios. These are development holdouts, not an untouched external benchmark. Text variants share templates and are not independent observations.','',
       '| Component | n | Precision | Recall | F1 | ROC-AUC | PR-AUC | Threshold |','|---|---:|---:|---:|---:|---:|---:|---:|']
for name,m in entries:
    lines.append(f"| {name} | {m['n']} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} | {m['roc_auc']:.3f} | {m['pr_auc']:.3f} | {m['threshold']:.3f} |")
lines+=['','Text positive = phishing, OTP scam or impersonation; legitimate = negative. Every transaction layer uses any simulated fraud as positive, including fraud outside that layer’s expertise. For fusion, review OR block is a positive detection. Block-only metrics evaluate the stricter action separately.','',
        '## Confusion matrices','', 'Rows = actual [legitimate, fraud]. Columns = predicted [legitimate, fraud]. Each cell below is [[TN, FP], [FN, TP]].','']
for name,m in entries: lines.append(f"- **{name}:** `{m['confusion_matrix']}`")
lines+=['','## Interpretation','',
 'The graph ablation compares the same XGBoost setup with and without graph features; the diagnostic combined model is not silently used as the behavioral layer. See network.json for before/after values.',
 '', 'Weighted fusion uses 0.35 text + 0.35 behavior + 0.20 network + 0.10 rules. A rule score ≥0.95 sets a 0.90 score floor. This intentionally double-counts some text evidence and makes no independence assumption. It is a transparent risk index, not a calibrated probability.',
 '', 'Threshold exploration is retained in fusion_initial_policy.json and fusion_f1_policy.json. Final review threshold maximizes validation F2 to favor recall. Block threshold uses a validation precision constraint. Earlier test results were observed during development, so the final test should be regarded as a development holdout; a fresh external benchmark is still required.',
 '', 'Validation and test behavior differ substantially because different held-out text templates activate rules differently. Strong validation block precision does not guarantee test block precision. Social-only fraud remains difficult: final test detection rates are shown below.','',
 json.dumps(get('fusion')['test_scenario_detection'],indent=2),
 '', '## Latency','', 'Measured with 32 sequential local requests across no-text, rules, baseline and BERT routes, warmed models and a small history. No throughput or bank-scale claim.','']
for name,stat in get('latency_benchmark')['latency_ms'].items(): lines.append(f"- {name}: mean {stat['mean']:.2f} ms; p95 {stat['p95']:.2f} ms.")
(root/'EVALUATION.md').write_text('\n'.join(lines)+'\n')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axes=plt.subplots(2,3,figsize=(12,7),layout='constrained')
for ax,(name,m) in zip(axes.flat,[entries[i] for i in [2,3,4,5,6,7]]):
    ax.imshow(m['confusion_matrix'],cmap='Blues')
    ax.set_title(name,fontsize=11); ax.set_xticks([0,1],['Legitimate','Fraud']);ax.set_yticks([0,1],['Legitimate','Fraud'])
    for i,row in enumerate(m['confusion_matrix']):
        for j,v in enumerate(row): ax.text(j,i,str(v),ha='center',va='center',color='white' if v>max(map(max,m['confusion_matrix']))*.5 else '#123',fontsize=14)
    ax.set_xlabel('Predicted');ax.set_ylabel('Actual')
fig.suptitle('Synthetic development holdout · confusion matrices',fontsize=15)
fig.savefig(root/'confusion_matrices.png',dpi=160)
print('Created EVALUATION.md and confusion_matrices.png')
