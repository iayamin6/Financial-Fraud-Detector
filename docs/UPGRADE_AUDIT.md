# Upgrade audit and implementation plan

Baseline inspected: origin/main 52b2d7d. Existing repository and models are retained.

| Capability | Baseline | Upgrade |
|---|---|---|
| NLP | Real DistilBERT fine-tuning, TF-IDF, regex, spaCy, MiniLM, English | Unicode preprocessing, safety-advisory coverage, scoped Bangla/transliterated rules, explicit confidence limits |
| Transaction ML | Genuine transaction XGBoost + training-only SMOTE | Preserve artifacts, independent supervised/anomaly evaluation, version manifest |
| Anomaly | Isolation Forest fit on legitimate training data | Separate metrics, drift/scenario validation; anomaly is not a fraud verdict |
| Graph | NetworkX fan-in/out, shared infrastructure, forwarding | Bounded circular-transfer paths and typed account/transaction/device relationship evidence |
| AML | No dedicated monitoring | Configurable velocity, near-threshold aggregation, mule/rapid movement, circularity alerts |
| Cases | Feedback only | Atomic automatic case creation, assignments, notes, optimistic revisions, audit events, human outcomes |
| Retrieval / LLM | Scam similarity only, no investigation RAG | Synthetic policy passages, FAISS + existing embeddings, local FLAN-T5, validated citations, explicit extractive fallback |
| Workflows | Missing | Real LangGraph nodes, SQLite checkpoints, conditional routing, durable human interrupt, retry/status |
| MLOps | Metrics and aggregate model hash | MLflow tracking, per-component hashes, drift/feedback monitoring, Docker and CI |
| Security | Loopback API, isolated cloud demo sessions | API key roles, fail-closed server deployment; persistent local/container cases; public demo remains session-isolated |

Implementation order: scoring additions → persistence/cases → RAG → workflow → API/UI → monitoring/deployment → evaluation/regression tests. No MCP server. No automatic retraining or regulatory reports. Public Streamlit is a synthetic session demo; durable organizational deployments use authenticated API and a mounted database volume.
