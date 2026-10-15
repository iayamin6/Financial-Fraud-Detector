# Upgrade validation

- Existing 20 regression tests and 12 upgrade tests pass locally (32 total).
- Public Streamlit verification on 2026-10-15: all five system checks passed, structuring created an AML case, and a real local-LLM investigation paused for review and completed after an inconclusive human outcome.
- Original cloud entrypoint tests pass: normal and scam decisions, five system checks, 50-row CSV batch, and visitor isolation.
- Investigation dashboard test passes: automatic case creation, graph rendering, LangGraph execution, local generation, human adjudication, audit and monitoring.
- Workflow tests reconstruct services over the same database and resume persisted human interrupts; failed runs can retry. Retrieval failure retains human review. Stale revisions and unauthorized roles are rejected.
- Separate supervised, anomaly, NLP, fusion and text-removal metrics are in `upgrade_evaluation.json`. Fusion development holdout remains precision 0.6866 / recall 0.6970 / F1 0.6917 / ROC-AUC 0.9406 / PR-AUC 0.6623 (720 transactions, 66 positive).
- The 40 constructed structuring/ordinary-payment scenarios pass. This tests intended rule behavior, not real-world AML precision.
- Retrieval recall@3 is 7/7 on seven author-created queries. Local FLAN-T5 selection produced a valid citation with verbatim grounding. The assistant emits cited policy text, not unconstrained allegations.
- Five MLflow evaluation runs were created locally, including configuration, metrics, version hashes and relevant saved model artifacts. Original models were not retrained as part of this upgrade.
- Docker configuration is supplied. The local container build failed with a Docker disk I/O error while the host disk was full. The clean Linux Docker build subsequently passed in [GitHub Actions run 38694496168](https://github.com/iayamin6/Financial-Fraud-Detector/actions/runs/38694496168), together with all regression and dashboard checks. Container runtime/load testing remains separate from this image-build check.

All reported predictive metrics use synthetic development data. No real banking, regulatory-compliance, multilingual-model or financial-loss-prevention claim is made.
