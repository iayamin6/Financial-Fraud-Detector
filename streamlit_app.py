"""Streamlit Community Cloud entrypoint: no separately hosted API required."""
import os
import runpy
from pathlib import Path

os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
os.environ['FRAUD_EMBEDDED'] = '1'
ROOT = Path(__file__).resolve().parent
runpy.run_path(str(ROOT / 'dashboard' / 'app.py'), run_name='__main__')
