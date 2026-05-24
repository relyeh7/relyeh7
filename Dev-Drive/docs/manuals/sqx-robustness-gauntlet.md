# Guía de Configuración: Guantelete de Robustez SQX Elite (XAUUSD)

> Este manual detalla la configuración técnica necesaria para filtrar estrategias en Strategy Quant X (SQX) y asegurar su robustez estadística en el mercado del Oro (XAUUSD).

## Introducción: La Filosofía del "Guantelete"
El Guantelete de Robustez no busca encontrar la estrategia con mayor beneficio, sino descartar aquellas que han sido víctimas del *curve-fitting* (sobre-optimización). Una estrategia robusta es aquella que sobrevive a cambios en el orden de las operaciones, variaciones en el mercado y optimizaciones fuera de muestra.

## Paso 1: Monte Carlo - Trade Level (Operación)
Esta prueba evalúa si el rendimiento de la estrategia depende de una secuencia específica de trades.

### Configuración en SQX:
1. Dirígete a la pestaña **Robustness Tests** -> **Monte Carlo (Trades)**.
2. Selecciona los siguientes métodos:
   - **Reshuffle trades**: Cambia el orden de las operaciones aleatoriamente.
   - **Skip trades (10%)**: Simula que la estrategia pierde o no ejecuta el 10% de las señales.
3. **Number of simulations**: 100.
4. **Confidence Level**: 95%.

### Criterio de Fallo:
- La estrategia falla si el **Max Drawdown** en el percentil 95 aumenta más de un **20%** respecto al backtest original.

## Paso 2: Monte Carlo - Market Level (Mercado)
Simula condiciones de mercado degradadas (spreads más altos y ejecución imperfecta).

### Configuración en SQX:
1. Ve a **Robustness Tests** -> **Monte Carlo (Market)**.
2. Configura las variaciones aleatorias:
   - **Spread**: Variación de ±20%.
   - **Slippage**: Variación de ±50%.
3. **Number of simulations**: 40-100.

### Criterio de Supervivencia:
- El **90%** de las simulaciones deben ser rentables (Profit > 0). Esto asegura que la estrategia no es "frágil" ante el ruido del broker.

## Paso 3: Walk Forward Matrix (WFM)
Verifica si la estrategia es capaz de adaptarse a nuevos datos mediante re-optimización periódica.

### Configuración en SQX:
1. Ve a la pestaña **Optimization** y selecciona **Walk Forward Matrix**.
2. **Matrix Parameters**:
   - **Runs**: De 5 a 15 (pasos de 1).
   - **OOS % (Out of Sample)**: De 10% a 30% (pasos de 5%).
3. **Fitness Function**: Return/DD o SQN.

### Umbrales de Aprobación (Pass):
- **WFM Efficiency**: Debe ser superior al **50%**.
- **Estabilidad**: El Profit Factor debe ser positivo y estable en al menos el **80%** de las celdas de la matriz resultante.
