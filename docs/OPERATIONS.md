# FraudShield operations and limitations

## Try the integrated workflow

On Streamlit, open **Investigations → Try an AML investigation → Load AML example**. Choose structuring, rapid forwarding or circular transfers. The existing scoring pipeline scores those payments and atomically creates cases for fraud-review or AML-review indicators. Select a case, view its graph/evidence, and click **Run investigation workflow**. The report remains `awaiting_review` until an analyst supplies an outcome and rationale. Case resolution does not move funds, submit a report or retrain a model.

The original demos, forms, CSV scoring, feedback, SHAP/LIME and API routes remain available. `aml_review_required` is a separate review signal; original fusion scores/tiers remain comparable with prior evaluations. An AML-only flag can create a case even if the fraud score is low. The RAG assistant uses seven original **synthetic** policy documents, not regulator-approved materials.

## Storage and access

Public Streamlit uses a different SQLite database and workflow-checkpoint file per browser session. Models and the read-only knowledge index are shared. Sessions are temporary; this is suitable for synthetic demos only. It is not a persistent multi-user bank case system.

The API stores durable cases and checkpoints in the configured SQLite path. In Docker, the named `fraud-data` volume survives container replacement. Back up both `fraud.sqlite3` and its `.checkpoints.sqlite` companion using SQLite-safe backup tooling while writes are paused. Do not delete the volume when preserving cases. No PostgreSQL or MongoDB is required.

API authentication has three single-organization roles: `scorer` can submit scores; `viewer` can read; `analyst` can investigate and adjudicate. All named keys belong to the same organization and analyst/viewer roles can access its cases. This is not tenant isolation or enterprise identity management. Audit events are append-only through the application, not tamper-proof against a database administrator.

Set secrets in the environment, never Git:

```bash
export FRAUD_SECURITY_MODE=authenticated
export FRAUD_API_KEYS='{"REPLACE_WITH_32_OR_MORE_RANDOM_CHARACTERS":{"actor":"analyst-name","role":"analyst"}}'
export FRAUD_DATABASE=/absolute/persistent/path/fraud.sqlite3
uvicorn api.main:app --host 127.0.0.1 --port 8765 --workers 1
```

Clients send `X-API-Key`. The separate local Streamlit dashboard reads `FRAUD_API_KEY` from its environment. Health checks are public; other API routes require a valid key in authenticated mode. Docker defaults to authenticated mode and fails closed without keys. Local development preserves the original loopback/no-key experience. Put TLS and organizational identity controls in front of a nonlocal API deployment. Do not expose local mode to the internet.

## Docker

Run `git lfs pull` first, then `docker compose up --build`. Supply `FRAUD_API_KEYS` before starting. The API binds to localhost port 8765 on the host. Model weights are embedded in the image; missing artifacts cause explicit startup failure. Models run on CPU. Container deployments require adequate memory for DistilBERT, embeddings, spaCy, and the lazily loaded FLAN-T5 generator.

## RAG and local LLM

MiniLM embeddings and FAISS retrieve relevant passages. FLAN-T5-small selects a cited passage with constrained decoding; final guidance quotes the selected passage exactly. This deliberately limits generation to evidence selection rather than free-form accusations. There are no external LLM calls, API keys or MCP server. Retrieval below the configured similarity cutoff abstains. Missing/invalid generation returns a labeled extractive fallback. Retrieval failure in a workflow produces an explicit missing-evidence report and still requires human review. Questions and cited source snapshots are saved as case audit events.

The LLM is not fine-tuned on financial investigations. English classifiers remain English; Bangla and transliterated Bangla support is scoped to configured credential-request rules. Script mixing alone never raises fraud risk. Risk/classifier scores are uncalibrated.

## Workflows and API additions

- `GET/POST /cases`, `GET/PATCH /cases/{id}`: list/create/read/update cases.
- `POST /cases/{id}/ask`: `{ "question": "..." }`, returns cited knowledge.
- `POST /cases/{id}/investigate`: starts or retrieves an active investigation.
- `GET /investigations/{run_id}`: persisted state/report/status.
- `POST /investigations/{run_id}/retry`: recover an interrupted run from checkpoints.
- `POST /investigations/{run_id}/resume`: `{ "revision": 1, "outcome": "inconclusive", "note": "Evidence still incomplete" }`.
- `GET /monitoring`: feature PSI, prediction distribution/PSI, adjudicated metrics.

Case transitions are `open → under_review → resolved`. Edits require the current revision to prevent silently overwriting another analyst. Active workflows must be resolved through their review endpoint. Resolved records cannot be silently rewritten. New outcomes require a separate reviewed process rather than automatic feedback ingestion. Restarting a service and constructing a new workflow object preserves checkpoints and human interrupts.

## MLOps

Install `pip install -e '.[mlops]'`. `python scripts/track_experiments.py` imports saved reports and actual model artifacts into local MLflow tracking, explicitly tagged as historical evaluation, not retraining. To track new training runs, enable `mlops.enabled` in config; training report writers invoke MLflow tracking with configs, metrics, artifacts and version hashes. Set `MLFLOW_TRACKING_URI` only if you intentionally want a remote tracker. MLflow is optional for inference and is not installed on the public Streamlit server.

`python scripts/evaluate_upgrade.py` evaluates the existing supervised classifier, anomaly detector, NLP, fusion and fixed-weight text ablation; it also checks synthetic AML scenarios and retrieval queries. `python scripts/export_reviewed_labels.py --output /secure/path/labels.json` exports resolved, non-inconclusive cases for a controlled future evaluation. No automatic retraining or model promotion occurs.

PSI compares recent data with synthetic training/reference distributions; it is an investigation signal, not a statistical guarantee. Case outcome metrics are selection-biased and not population performance. Review new models on an independent holdout before promotion. Deploying changed scoring source/config/models changes the stored version fingerprint; old uncached SHAP/LIME explanations cannot be regenerated without the original artifacts. Case reports retain original score/evidence snapshots.

## CI and Streamlit

GitHub Actions tests the API, models, AML, cases, workflow recovery, roles and dashboards. Streamlit independently follows `main`, so a push updates the live app. CI is not a deployment gate unless branch protection is configured. Use PRs and required checks when multiple contributors work on the project. Dependency edits trigger a longer cloud rebuild. No deployment token is committed.
