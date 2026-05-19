import pandas as pd
import numpy as np
import pytest
from core.data_forge import DataForge

def test_apply_correlation_break():
    df = pd.DataFrame({
        'time': pd.to_datetime(['2026-01-01', '2026-01-02']),
        'open': [2000.0, 2010.0],
        'high': [2020.0, 2030.0],
        'low': [1990.0, 2000.0],
        'close': [2010.0, 2020.0],
        'tick_volume': [100, 110],
        'spread': [10, 10],
        'real_volume': [0, 0]
    })
    forge = DataForge()
    df_stress = forge.apply_correlation_break(df, noise_factor=0.1)
    assert not df_stress['close'].equals(df['close'])
