The generator (`python -m fraud.data`) creates original, deterministic synthetic data.
No customer records or downloaded PaySim rows are included. Fraud labels represent
simulated social engineering, behavioral anomalies, or mule scenarios. Labels and
scenario identifiers must never be included in inference features.

Text train/validation/test partitions hold out complete template families. Transaction
partitions are chronological. Texts are attached only from their corresponding partition.
The test set still shares a generator with training and is a demo benchmark, not
external validation. The class distribution of standalone text data (75% scam) is
intentionally different from transaction prevalence (~10% fraud); probabilities are
not calibrated real-world fraud likelihoods.

Use one normalized currency. The API intentionally has no currency conversion.
External data must map to the API schema, have a lawful provenance, and preserve
chronological history. Real SMS spam labels should not be relabeled as financial fraud
without review. PaySim is an optional future external benchmark, not silently substituted.
