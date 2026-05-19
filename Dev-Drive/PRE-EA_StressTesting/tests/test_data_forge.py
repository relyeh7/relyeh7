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

def test_correlation_break_is_brownian():
    # Create a dataframe with more rows to see the cumulative effect
    n = 100
    df = pd.DataFrame({
        'time': pd.to_datetime(np.arange(n), unit='D'),
        'open': np.ones(n) * 100.0,
        'high': np.ones(n) * 105.0,
        'low': np.ones(n) * 95.0,
        'close': np.ones(n) * 100.0,
        'tick_volume': np.ones(n) * 100,
        'spread': np.ones(n) * 10,
        'real_volume': np.zeros(n)
    })
    forge = DataForge(init_mt5=False)
    df_stress = forge.apply_correlation_break(df, noise_factor=0.1)
    
    # Calculate noise applied to 'close'
    noise = df_stress['close'] - df['close']
    
    # In Brownian motion (np.cumsum(normal)), the variance should grow with time.
    # A simple way to check if it's cumulative: 
    # if it was independent white noise, np.diff(noise) would be normal(0, sqrt(2)*sigma).
    # If it is np.cumsum(normal), then np.diff(noise) should be the original normal(0, sigma).
    # More importantly, we check if the SAME noise is applied to all columns (OHLC structure preservation)
    
    diff_open = df_stress['open'] - df['open']
    diff_close = df_stress['close'] - df['close']
    
    # Same noise series should be applied to all columns (before clipping and integrity fix)
    # However, since we apply it to all columns, the DIFFERENCE between them should be preserved
    # unless clipping or integrity fix kicked in.
    # Let's check if the path is the same for open and close
    pd.testing.assert_series_equal(diff_open, diff_close, obj="Noise should be same for all columns", check_names=False)
    
    # Check that it is cumulative (Brownian)
    # If noise = cumsum(steps), then steps = diff(noise)
    steps = noise.diff().dropna()
    # If it was white noise, diff(noise) would be much more volatile than noise itself
    # If it is Brownian, noise is much more "wandering" than steps.
    assert noise.std() > steps.std() * 2 # Heuristic: Brownian motion spreads out

def test_apply_execution_degradation():
    df = pd.DataFrame({
        'time': pd.to_datetime(['2026-01-01']),
        'open': [2000.0], 'high': [2010.0], 'low': [1990.0], 'close': [2000.0],
        'tick_volume': [100], 'spread': [10], 'real_volume': [0]
    })
    forge = DataForge(init_mt5=False)
    df_stress = forge.apply_execution_degradation(df, spread_mult=5, vol_mult=0.5)
    assert df_stress.iloc[0]['spread'] == 50
    assert df_stress.iloc[0]['tick_volume'] == 50

def test_apply_execution_degradation_comprehensive():
    df = pd.DataFrame({
        'time': pd.to_datetime(['2026-01-01', '2026-01-02']),
        'open': [2000.0, 2005.0],
        'tick_volume': [100, 201],
        'spread': [10, 12],
        'real_volume': [500, 600]
    })
    forge = DataForge(init_mt5=False)
    # Test with rounding and multiple rows
    df_stress = forge.apply_execution_degradation(df, spread_mult=2.5, vol_mult=0.3)
    
    # Row 0: 10 * 2.5 = 25; 100 * 0.3 = 30
    assert df_stress.iloc[0]['spread'] == 25
    assert df_stress.iloc[0]['tick_volume'] == 30
    
    # Row 1: 12 * 2.5 = 30; 201 * 0.3 = 60.3 -> 60 (int cast)
    assert df_stress.iloc[1]['spread'] == 30
    assert df_stress.iloc[1]['tick_volume'] == 60
    
    # real_volume should be untouched in current implementation
    assert df_stress.iloc[0]['real_volume'] == 500
    
    # Test vol_mult = 0
    df_zero = forge.apply_execution_degradation(df, spread_mult=1, vol_mult=0)
    assert (df_zero['tick_volume'] == 0).all()

def test_apply_black_swan_v2():
    # 2016 velas (representando 7 días exactos en M5)
    n = 2016
    df = pd.DataFrame({
        'time': pd.to_datetime(range(n), unit='m', origin='2026-01-01'),
        'open': [2000.0]*n, 'high': [2001.0]*n, 'low': [1999.0]*n, 'close': [2000.0]*n,
        'tick_volume': [100]*n, 'spread': [10]*n, 'real_volume': [0]*n
    })
    forge = DataForge(init_mt5=False)
    total_pips = 800
    df_stress = forge.apply_black_swan(df, total_pips=total_pips)
    
    # 1. Verificar Delta total en 7 días (800 pips = 80.0 USD)
    expected_delta = total_pips * 0.1
    # Close de la última vela - Open de la primera
    actual_delta = df_stress.iloc[-1]['close'] - df_stress.iloc[0]['open']
    assert pytest.approx(actual_delta) == expected_delta
    
    # 2. Verificar Monotonicidad (Cero retrocesos)
    # El Low de cada vela debe ser mayor al Low de la anterior
    assert (df_stress['low'].diff().dropna() > 0).all()
    
    # 3. Verificar estructura de vela
    assert (df_stress['high'] > df_stress['open']).all()
    assert (df_stress['high'] > df_stress['close']).all()
    assert (df_stress['low'] < df_stress['open']).all()
    
    # 4. Verificar preservación de volumen y spread
    assert (df_stress['tick_volume'] == 100).all()
    assert (df_stress['spread'] == 10).all()

def test_apply_black_swan_long_duration():
    # Probar que la pendiente se mantiene sobre 30 días
    n = 30 * 24 * 12 # 30 días M5
    df = pd.DataFrame({
        'time': pd.to_datetime(range(n), unit='m'),
        'open': [2000.0]*n, 'high': [2000.0]*n, 'low': [2000.0]*n, 'close': [2000.0]*n,
        'tick_volume': [100]*n, 'spread': [10]*n, 'real_volume': [0]*n
    })
    forge = DataForge(init_mt5=False)
    df_stress = forge.apply_black_swan(df, total_pips=800)
    
    # Velocity: 800 pips / 7 days. In 30 days should be (30/7)*800 pips
    expected_delta = (30 / 7) * 800 * 0.1
    actual_delta = df_stress.iloc[-1]['close'] - df_stress.iloc[0]['open']
    assert pytest.approx(actual_delta) == expected_delta
