"""Fraud Signals: conservative thread defaults for mixed native ML runtimes."""
import os
# Set before numpy/torch imports. Override explicitly for benchmarked deployments.
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
