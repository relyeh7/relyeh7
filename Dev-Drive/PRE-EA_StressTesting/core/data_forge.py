import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time

class DataForge:
    def __init__(self):
        if not mt5.initialize():
            print("Error al inicializar MetaTrader 5:", mt5.last_error())
            raise Exception("MT5 initialization failed")

    def fetch_rates(self, symbol, timeframe, days):
        """Obtiene datos históricos del símbolo origen."""
        utc_to = time.time()
        utc_from = utc_to - (days * 24 * 3600)
        
        rates = mt5.copy_rates_range(symbol, timeframe, int(utc_from), int(utc_to))
        if rates is None or len(rates) == 0:
            print(f"No se pudieron obtener datos para {symbol}")
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def apply_volatility_stress(self, df, factor=2.5):
        """Expande la volatilidad (mechas y cuerpo) manteniendo el Open."""
        df_stress = df.copy()
        # Calculamos la diferencia respecto al Open
        df_stress['high'] = df_stress['open'] + (df_stress['high'] - df_stress['open']) * factor
        df_stress['low'] = df_stress['open'] - (df_stress['open'] - df_stress['low']) * factor
        df_stress['close'] = df_stress['open'] + (df_stress['close'] - df_stress['open']) * factor
        return df_stress

    def apply_gap_stress(self, df, prob=0.01, max_gap_mult=3.0):
        """Inyecta gaps aleatorios basados en la volatilidad local."""
        df_stress = df.copy()
        n = len(df_stress)
        # Generar máscara de gaps
        gaps_mask = np.random.random(n) < prob
        
        # Calcular tamaño de gaps (ATR-like local)
        local_vol = (df_stress['high'] - df_stress['low']).rolling(window=20).mean().fillna(method='bfill')
        
        cumulative_offset = 0.0
        new_opens = []
        new_highs = []
        new_lows = []
        new_closes = []

        for i in range(n):
            if gaps_mask[i]:
                # Gap Up o Down aleatorio
                direction = 1 if np.random.random() > 0.5 else -1
                gap_size = direction * np.random.random() * max_gap_mult * local_vol.iloc[i]
                cumulative_offset += gap_size
            
            new_opens.append(df_stress.iloc[i]['open'] + cumulative_offset)
            new_highs.append(df_stress.iloc[i]['high'] + cumulative_offset)
            new_lows.append(df_stress.iloc[i]['low'] + cumulative_offset)
            new_closes.append(df_stress.iloc[i]['close'] + cumulative_offset)

        df_stress['open'] = new_opens
        df_stress['high'] = new_highs
        df_stress['low'] = new_lows
        df_stress['close'] = new_closes
        
        return df_stress

    def apply_correlation_break(self, df, noise_factor=0.05):
        """Inyecta ruido estocástico para romper patrones."""
        df_stress = df.copy()
        n = len(df_stress)
        # Caminata aleatoria (Random Walk)
        noise = np.cumsum(np.random.normal(0, noise_factor, n))
        # Aplicar ruido al precio base
        df_stress['open'] += noise
        df_stress['high'] += noise
        df_stress['low'] += noise
        df_stress['close'] += noise
        return df_stress

    def create_custom_symbol(self, source_symbol, target_symbol, df_stress):
        """Carga los datos estresados en un nuevo símbolo personalizado en MT5."""
        # 1. Crear símbolo si no existe
        if mt5.symbol_info(target_symbol) is None:
            if not mt5.symbol_custom_create(target_symbol, "StressTests", source_symbol):
                print(f"Error al crear {target_symbol}:", mt5.last_error())
                return False
        
        # 2. Preparar datos para MT5
        # Convertir dataframe de vuelta a estructura de tuplas (MqlRates)
        rates_to_add = []
        for index, row in df_stress.iterrows():
            rates_to_add.append((
                int(row['time'].timestamp()),
                row['open'],
                row['high'],
                row['low'],
                row['close'],
                int(row['tick_volume']),
                int(row['spread']),
                int(row['real_volume'])
            ))
        
        # 3. Reemplazar datos
        res = mt5.symbol_custom_rates_replace(target_symbol, rates_to_add[0][0], rates_to_add[-1][0], rates_to_add)
        if res < 0:
            print(f"Error al cargar datos en {target_symbol}:", mt5.last_error())
            return False
        
        mt5.symbol_select(target_symbol, True)
        return True

    def shutdown(self):
        mt5.shutdown()
