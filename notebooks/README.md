The reproducible experiments live in `scripts/` rather than depending on hidden
notebook state. Run stages in order, then inspect machine-readable results in
`reports/`. This directory is reserved for exploratory notebooks against the same
saved train/validation/test partitions. Do not fit encoders or SMOTE on test data.
