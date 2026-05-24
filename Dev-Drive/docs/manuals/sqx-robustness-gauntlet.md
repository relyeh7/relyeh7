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
