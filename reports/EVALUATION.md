# Evaluation results

All data are original synthetic scenarios. These are development holdouts, not an untouched external benchmark. Text variants share templates and are not independent observations.

| Component | n | Precision | Recall | F1 | ROC-AUC | PR-AUC | Threshold |
|---|---:|---:|---:|---:|---:|---:|---:|
| TF-IDF baseline | 80 | 0.800 | 1.000 | 0.889 | 0.842 | 0.951 | 0.500 |
| DistilBERT | 80 | 0.857 | 1.000 | 0.923 | 0.988 | 0.996 | 0.500 |
| Full text layer | 80 | 0.923 | 1.000 | 0.960 | 1.000 | 1.000 | 0.500 |
| Behavioral ensemble | 720 | 0.479 | 0.515 | 0.496 | 0.765 | 0.540 | 0.500 |
| Network formula | 720 | 1.000 | 0.333 | 0.500 | 0.667 | 0.394 | 0.500 |
| XGBoost + graph (ablation) | 720 | 0.896 | 0.652 | 0.754 | 0.830 | 0.724 | 0.500 |
| Fusion: review or block | 720 | 0.687 | 0.697 | 0.692 | 0.941 | 0.662 | 0.400 |
| Fusion: block only | 720 | 0.800 | 0.061 | 0.113 | 0.941 | 0.662 | 0.575 |

Text positive = phishing, OTP scam or impersonation; legitimate = negative. Every transaction layer uses any simulated fraud as positive, including fraud outside that layer’s expertise. For fusion, review OR block is a positive detection. Block-only metrics evaluate the stricter action separately.

## Confusion matrices

Rows = actual [legitimate, fraud]. Columns = predicted [legitimate, fraud]. Each cell below is [[TN, FP], [FN, TP]].

- **TF-IDF baseline:** `[[5, 15], [0, 60]]`
- **DistilBERT:** `[[10, 10], [0, 60]]`
- **Full text layer:** `[[15, 5], [0, 60]]`
- **Behavioral ensemble:** `[[617, 37], [32, 34]]`
- **Network formula:** `[[654, 0], [44, 22]]`
- **XGBoost + graph (ablation):** `[[649, 5], [23, 43]]`
- **Fusion: review or block:** `[[633, 21], [20, 46]]`
- **Fusion: block only:** `[[653, 1], [62, 4]]`

## Interpretation

The graph ablation compares the same XGBoost setup with and without graph features; the diagnostic combined model is not silently used as the behavioral layer. See network.json for before/after values.

Weighted fusion uses 0.35 text + 0.35 behavior + 0.20 network + 0.10 rules. A rule score ≥0.95 sets a 0.90 score floor. This intentionally double-counts some text evidence and makes no independence assumption. It is a transparent risk index, not a calibrated probability.

Threshold exploration is retained in fusion_initial_policy.json and fusion_f1_policy.json. Final review threshold maximizes validation F2 to favor recall. Block threshold uses a validation precision constraint. Earlier test results were observed during development, so the final test should be regarded as a development holdout; a fresh external benchmark is still required.

Validation and test behavior differ substantially because different held-out text templates activate rules differently. Strong validation block precision does not guarantee test block precision. Social-only fraud remains difficult: final test detection rates are shown below.

{
  "behavior": 0.9545454545454546,
  "legit": 0.03211009174311927,
  "mule": 0.6818181818181818,
  "social": 0.45454545454545453
}

## Latency

Measured with 32 sequential local requests across no-text, rules, baseline and BERT routes, warmed models and a small history. No throughput or bank-scale claim.

- text: mean 7.57 ms; p95 19.60 ms.
- behavioral: mean 4.92 ms; p95 5.35 ms.
- network: mean 0.06 ms; p95 0.09 ms.
- fusion: mean 0.01 ms; p95 0.01 ms.
- total_pipeline: mean 12.56 ms; p95 24.77 ms.
- http_round_trip: mean 15.86 ms; p95 28.59 ms.
