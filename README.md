# FraudShield

Financial fraud detection with transaction scoring and an investigation workspace.

A payment can look ordinary and still be part of a scam. The amount might be small, the account might be old, and nothing in the transaction record explains that someone was asked to share an OTP. FraudShield looks at the message alongside the payment history and account connections to catch that missing context.

It returns a risk score with reasons, then lets an analyst investigate the alert and record an outcome. The project includes trained models, a FastAPI backend, and a Streamlit dashboard you can try without setting anything up.

[Try the live app](https://financial-fraud-detector-iayamin6.streamlit.app/) · [Evaluation results](reports/EVALUATION.md) · [Architecture](ARCHITECTURE.md)

## Try it

Start with **Try a demo** in the dashboard:

1. Run **Try normal payment**. It should return low risk.
2. Run **Try OTP scam**. The amount stays the same, but the message asks for a secret code. It should return high risk, with the matched request shown in the explanation.
3. Click **Run system check** to check scoring, saved results, and explanations. All five checks should pass.

To explore an investigation, open **Investigations**, choose an AML example, and click **Load AML example**. You can inspect its transfers, run the investigation workflow, and record a review outcome. For batch scoring, upload the [50-payment sample CSV](data/fraud_test_50_unique.csv) from **Upload a CSV**.

The public app is a synthetic-data demo. It isn't connected to a bank and doesn't move or block money. Each browser session has temporary storage, so saved checks and cases may disappear when the session ends or the app restarts.

## How a payment gets checked

**The message.** Rules check for direct OTP/PIN requests and other known scam phrases first. A TF-IDF classifier handles the lightweight screening, with fine-tuned DistilBERT used where the routing requires it. The text layer also uses spaCy entities, urgency markers, and similarity to known scam examples. It distinguishes legitimate text, OTP scams, phishing, and impersonation.

**The behavior.** XGBoost and Isolation Forest use features such as amount relative to history, recent payment count and total, new recipients, account age, and device or country changes. XGBoost learns from labeled examples; Isolation Forest adds a measure of unusual behavior.

**The relationships.** A NetworkX graph tracks prior transfers and shared infrastructure. It provides signals such as a recipient's previous flags, incoming and outgoing connections, and rapid forwarding. Separate AML rules look for near-threshold transfers, possible mule patterns, and circular movement of funds.

**The result.** The scoring formula combines text, behavior, network, and rule scores with weights of `0.35 / 0.35 / 0.20 / 0.10`. A strong credential-request rule can apply a high-risk floor. The result is a pass, review, or block *recommendation*, with the contribution of each layer available to inspect. AML can independently send a payment for review even when the combined fraud score is low.

History features only use events earlier than the payment being scored. SHAP explains the behavioral score, LIME explains the routed text score, and rule matches provide the exact text that triggered them.

## What happens after an alert

Review-worthy payments create cases. The investigation workspace supports assignments, notes, relationship graphs, saved evidence, and an audit trail. Cases move from open to under review to resolved.

LangGraph coordinates evidence collection, guidance retrieval, and report preparation. It pauses for a human decision and saves checkpoints so an interrupted investigation can resume. Resolving a case requires an outcome and a rationale.

The guidance assistant uses MiniLM embeddings and FAISS to search a small set of synthetic investigation policies. A local FLAN-T5 model selects supporting evidence; the answer quotes the selected passage and includes its citation. This keeps guidance traceable, though it also limits the assistant to the material in that small collection.

The monitoring page shows distribution shifts and available analyst-reviewed results. MLflow records experiments and model artifacts, while stored model fingerprints identify which version produced a score. Feedback can be exported for later evaluation; it doesn't automatically retrain the models.

## Stack

| Part | Tools |
|---|---|
| Language and data | Python, pandas, NumPy |
| Text | Hugging Face Transformers / DistilBERT, scikit-learn, spaCy, Sentence Transformers |
| Transaction models | XGBoost, Isolation Forest, training-only SMOTE |
| Graphs and explanations | NetworkX, SHAP, LIME |
| Investigations | LangGraph, FAISS, FLAN-T5-small |
| API and storage | FastAPI, Pydantic, Uvicorn, SQLite |
| Dashboard | Streamlit |
| Tracking and deployment | MLflow, pytest, Docker, GitHub Actions, Streamlit Community Cloud |

SQLite stores scores, cases, feedback, audit events, and workflow checkpoints. The standalone API supports persistent storage and API-key roles for scorers, viewers, and analysts. See [operations](docs/OPERATIONS.md) for authentication and Docker setup.

## Results and what they mean

The dataset contains **3,600 original synthetic transactions** and **736 text examples**. It is included in the repository; it is not PaySim or real customer data. Transactions are split chronologically, and text splits keep template variants together. [Data provenance](data/provenance.json) describes the source.

On the 720-transaction development holdout, the combined score flagged **46 of 66 fraud cases**, with **21 false positives**. Here, either a review or block recommendation counts as a positive detection.

| Precision | Recall | F1 | ROC-AUC | PR-AUC |
|---:|---:|---:|---:|---:|
| 0.687 | 0.697 | 0.692 | 0.941 | 0.662 |

These results show where the approach works and where it falls short. Recall on social-engineering-only scenarios is about 45%, so that remains a substantial gap. The holdout was examined during development, and text examples come from a small number of templates. These numbers should not be treated as expected performance at a bank.

The [evaluation report](reports/EVALUATION.md) includes individual model results and confusion matrices. The [upgrade validation](reports/UPGRADE_VALIDATION.md) covers AML scenarios, retrieval, workflow recovery, dashboard checks, and deployment verification.

A few other limits matter:

- Scores are risk indices, not calibrated probabilities. An anomaly or an AML flag isn't proof of fraud.
- The trained text model is English-focused. Bangla and transliterated Bangla support consists of limited credential-request rules.
- Missing text contributes zero under the fixed fusion weights, which can reduce sensitivity.
- The retrieval collection contains synthetic guidance, not regulatory advice.
- The backend uses a single scoring worker and SQLite. Larger histories, concurrent users, and real transaction feeds need further engineering and testing.

The next useful step is evaluation on independent, realistically imbalanced data, followed by calibration and threshold tuning. That would say more about practical value than adding another model to the pipeline.

## Run locally

Use Python 3.11 or 3.12 and install Git LFS before cloning; the trained weights are stored with LFS.

```bash
git lfs install
git clone https://github.com/iayamin6/Financial-Fraud-Detector.git
cd Financial-Fraud-Detector
git lfs pull

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

This starts the same embedded version used by the live demo. It doesn't need a separate API process. The first startup takes longer because it loads the models.

To use the API and dashboard separately, stop the embedded app and run:

```bash
python scripts/run_api.py
```

In a second terminal, activate the same environment and run:

```bash
python scripts/seed_demo.py
python scripts/run_dashboard.py
```

The dashboard is at [localhost:8501](http://127.0.0.1:8501), and interactive API documentation is at [localhost:8765/docs](http://127.0.0.1:8765/docs). On macOS, XGBoost may also need `brew install libomp`.

Model paths, thresholds, weights, and history windows are in [`config.yaml`](config.yaml). For persistent deployment, API keys, and Docker, follow the [operations guide](docs/OPERATIONS.md). The local API defaults to loopback development mode; configure authenticated mode before exposing it elsewhere.

## Tests and experiments

After installing the dependencies:

```bash
pip install pytest
python -m pytest -q
python scripts/test_cloud.py
python scripts/test_investigation_dashboard.py
python scripts/evaluate_upgrade.py
```

To rebuild the models, stop the API before replacing artifacts and run these stages in order:

```bash
python -m fraud.data
python scripts/train_text.py
python scripts/train_behavior.py
python scripts/train_network.py
python scripts/evaluate_fusion.py
python scripts/calibrate_policy.py
python scripts/evaluate_fusion.py
python scripts/verify_explanations.py
```

Training downloads the base text checkpoint. Supplied inference artifacts load locally. Review the reports after each stage; exact numerical results may vary across devices.

For optional experiment tracking, install `pip install -e '.[mlops]'`. See the [MLflow instructions](docs/OPERATIONS.md#mlops) for recording new runs or importing existing evaluations.

GitHub Actions runs the regression tests, dashboard checks, and Docker build. Streamlit separately watches `main` and updates the live app when changes are pushed; CI is not currently a deployment gate.

## Finding your way around

- [`fraud/`](fraud/) — scoring layers, AML rules, storage, investigations, and monitoring
- [`api/`](api/) — request validation and HTTP endpoints
- [`dashboard/`](dashboard/) — Streamlit pages
- [`scripts/`](scripts/) — training, evaluation, and demo checks
- [`tests/`](tests/) — regression tests
- [`data/`](data/) and [`models/`](models/) — synthetic datasets and saved artifacts
- [`reports/`](reports/) — metrics, confusion matrices, and validation notes
- [`knowledge/`](knowledge/) — the synthetic policy collection used for retrieval

The [architecture notes](ARCHITECTURE.md) cover scoring and data-handling details. The [operations guide](docs/OPERATIONS.md) covers case workflows, API additions, storage, and deployment limits.
