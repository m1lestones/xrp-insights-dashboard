import pandas as pd
from src.processing import compute_txn_per_minute, compute_avg_fee


def test_empty_frames():
    empty = pd.DataFrame()
    assert compute_txn_per_minute(empty).empty
    assert compute_avg_fee(empty).empty
