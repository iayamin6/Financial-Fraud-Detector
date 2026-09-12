from pathlib import Path
import pandas as pd
from fraud.config import load_config

def test_partitions_hold_out_templates_and_time():
    root=Path(load_config()['paths']['data'])
    text=pd.read_csv(root/'texts.csv')
    assert text.groupby('template_id').split.nunique().max()==1
    tx=pd.read_csv(root/'transactions.csv')
    assert tx.transaction_id.is_unique
    assert tx.timestamp.is_monotonic_increasing
    assert tx[tx.split=='train'].timestamp.max()<tx[tx.split=='validation'].timestamp.min()
    assert tx[tx.split=='validation'].timestamp.max()<tx[tx.split=='test'].timestamp.min()
    assert .05<tx.fraud.mean()<.15
