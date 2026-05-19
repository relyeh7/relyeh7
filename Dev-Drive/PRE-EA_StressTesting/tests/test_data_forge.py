import pandas as pd
import numpy as np
import pytest
from core.data_forge import DataForge

def test_apply_correlation_break():
    # Use very low prices to force minimum price clipping
    df = pd.DataFrame({
        'time': pd.to_datetime(['2026-01-01', '2026-01-02']),
        'open': [0.05, 0.05],
        'high': [0.10, 0.10],
        'low': [0.02, 0.02],
        'close': [0.07, 0.07],
        'tick_volume': [100, 110],
        'spread': [10, 10],
        'real_volume': [0, 0]
    })
    forge = DataForge(init_mt5=False)
    # Large noise factor to ensure integrity violations and price clipping
    df_stress = forge.apply_correlation_break(df, noise_factor=5.0)
    
    # Assert noise is applied
    assert not df_stress['close'].equals(df['close'])
    
    # Assert minimum price
    assert (df_stress[['open', 'high', 'low', 'close']] >= 0.01).all().all()
    
    # Assert candle integrity
    assert (df_stress['high'] >= df_stress['open']).all()
    assert (df_stress['high'] >= df_stress['close']).all()
    assert (df_stress['high'] >= df_stress['low']).all()
    assert (df_stress['low'] <= df_stress['open']).all()
    assert (df_stress['low'] <= df_stress['close']).all()
