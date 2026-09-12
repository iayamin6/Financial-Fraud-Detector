"""Use the same scoring engine in Streamlit, with visitor-isolated storage."""
import copy
import csv
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit, parse_qs
import streamlit as st
from pydantic import ValidationError
from fraud.config import load_config
from fraud.engine import Engine, Conflict, NotFound
from fraud.schemas import Transaction, BatchRequest, Feedback
from fraud.store import Store

@st.cache_resource(show_spinner='Loading the fraud detection models…')
def shared_models():
    directory = TemporaryDirectory(prefix='fraud-models-')
    cfg = load_config()
    cfg['paths']['database'] = str(Path(directory.name) / 'empty.sqlite3')
    return Engine(cfg), directory


def session_engine():
    if '_visitor_engine' not in st.session_state:
        base, root = shared_models()
        directory = TemporaryDirectory(prefix='visitor-', dir=root.name)
        engine = copy.copy(base)
        engine.store = Store(Path(directory.name) / 'checks.sqlite3')
        st.session_state['_visitor_engine'] = engine
        st.session_state['_visitor_directory'] = directory
    return st.session_state['_visitor_engine']


def dispatch(engine, method, path, **kwargs):
    """Transport adapter only: the five model layers are unchanged."""
    parts = urlsplit(path)
    try:
        if method == 'GET':
            if parts.path == '/health': return {'status': 'ready', 'model_version': engine.version}
            if parts.path == '/policy': return engine.cfg['fusion']
            if parts.path == '/metrics': return engine.metrics()
            if parts.path == '/transactions':
                limit = int(parse_qs(parts.query).get('limit', ['100'])[0])
                if not 1 <= limit <= 1000: raise ValueError('Invalid result limit')
                return engine.recent(limit)
        elif method == 'POST':
            if parts.path == '/score': return engine.score_many([Transaction.model_validate(kwargs['json'])])[0]
            if parts.path == '/score/batch':
                data = kwargs['json']
                records = BatchRequest.model_validate(data).transactions if isinstance(data, dict) else [Transaction.model_validate(r) for r in data]
                return engine.score_many(records)
            if parts.path == '/score/batch/csv':
                raw = kwargs['files']['file'][1]
                if isinstance(raw, str): raw = raw.encode('utf-8')
                if len(raw) > engine.cfg['api']['csv_max_bytes']: raise ValueError('CSV exceeds configured byte limit')
                reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
                if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)): raise ValueError('CSV needs unique column headers')
                records = []
                for row in reader:
                    if len(records) >= engine.cfg['api']['batch_limit']: raise ValueError('CSV exceeds batch limit')
                    records.append(Transaction.model_validate({k: None if v == '' else v for k, v in row.items()}))
                return engine.score_many(records)
            if parts.path.startswith('/explain/'): return engine.explain(parts.path.removeprefix('/explain/'))
            if parts.path == '/feedback': return engine.feedback(Feedback.model_validate(kwargs['json']))
        raise NotFound('Unknown operation')
    except (ValidationError, ValueError, UnicodeError, csv.Error) as exc:
        raise RuntimeError(str(exc)) from exc
