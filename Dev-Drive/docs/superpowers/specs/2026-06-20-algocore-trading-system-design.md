# AlgoCore — Sistema de Trading Algorítmico con IA/ML
**Spec aprobado:** 2026-06-20  
**Arquitectura:** Microservicios con Message Bus  
**Estado:** Diseño aprobado, pendiente de implementación

---

## 1. Objetivo

Construir un sistema de trading algorítmico automatizado nuevo desde cero, que opere en crypto (Bitget + Binance) y Forex/XAUUSD (MT5), combinando estrategias técnicas clásicas con ML predictivo y Reinforcement Learning, coordinados por un orquestador LLM. El sistema tiene autonomía adaptativa: autónomo en estrategias probadas, semi-autónomo en estrategias nuevas o condiciones inusuales.

Los proyectos existentes (BitgetBot, Bot2026, PRE-EA_StressLab, ICT_CRT_System) se usan como referencia y fuente de datos históricos, no como base de código.

---

## 2. Mercados y Exchanges

| Mercado | Exchange/Plataforma | Pares Iniciales |
|---|---|---|
| Crypto | Bitget | ETH/USDT, BTC/USDT |
| Crypto | Binance | BTC/USDT, BNB/USDT |
| Forex | MT5 (broker existente) | XAUUSD, EURUSD, GBPUSD |
| Commodities | MT5 | XAGUSD |

El router de exchange selecciona automáticamente por fee, liquidez y disponibilidad de API.

---

## 3. Arquitectura — Microservicios con Message Bus

```
┌─────────────┐    ┌─────────────┐    ┌──────────────┐
│ data-service│    │  ml-service │    │  rl-service  │
│ (feeds,     │    │ (LSTM, XGB, │    │ (PPO/SAC     │
│  sentiment) │    │  Ensemble)  │    │  Gym env)    │
└──────┬──────┘    └──────┬──────┘    └──────┬───────┘
       │                  │                   │
       └──────────────────▼───────────────────┘
                   MESSAGE BUS (Redis Streams)
                          │
           ┌──────────────▼──────────────┐
           │      orchestrator-service    │
           │  (LLM: Claude/Gemini)        │
           │  Ciclo 15min + event-driven  │
           └──────┬──────────────┬────────┘
                  │              │
     ┌────────────▼──┐    ┌──────▼──────────┐
     │ executor/crypto│    │ executor/forex  │
     │ Bitget+Binance │    │ MT5 Python Bridge│
     └────────────┬──┘    └──────┬───────────┘
                  │              │
           ┌──────▼──────────────▼──────┐
           │    risk-service            │
           │  (reglas globales de riesgo)│
           └──────────────┬─────────────┘
                          │
           ┌──────────────▼─────────────┐
           │    dashboard-service        │
           │  FastAPI + React + Telegram │
           └────────────────────────────┘
```

### Infraestructura
- **Message Bus:** Redis Streams (ligero, persistente, suficiente para este volumen)
- **Base de datos:** PostgreSQL — historial de trades, métricas de modelos, logs del orquestador
- **Despliegue:** Docker Compose — todo el sistema levanta con `docker-compose up`
- **Entorno:** Corre en máquina local o VPS (~$20-40/mes para VPS Ubuntu)

---

## 4. Estructura de Carpetas

```
AlgoCore/
├── services/
│   ├── data/
│   │   ├── feeds/         # WebSocket Bitget, Binance, MT5
│   │   ├── sentiment/     # Fear & Greed, NewsAPI, scraping
│   │   └── indicators/    # ta-lib: RSI, ATR, MACD, FVG, ICT
│   ├── ml/
│   │   ├── models/        # XGBoost, LSTM, Transformer
│   │   ├── training/      # Pipeline reentrenamiento automático
│   │   ├── inference/     # Servidor de predicciones en tiempo real
│   │   └── tracking/      # MLflow — versiones y métricas
│   ├── rl/
│   │   ├── env/           # Gym environment con datos reales
│   │   ├── agents/        # PPO, SAC (Stable-Baselines3)
│   │   ├── training/      # Ciclo simulación → paper → live
│   │   └── validation/    # Criterios de promoción a producción
│   ├── orchestrator/
│   │   ├── agent.py       # LLM decision engine (Claude/Gemini)
│   │   ├── tools.py       # Tool-use schema para decisiones
│   │   ├── rules.py       # Fallback determinista sin API
│   │   └── context.py     # Builder del prompt de mercado
│   ├── executor/
│   │   ├── crypto/
│   │   │   ├── bitget.py  # BitgetClient (basado en BitgetBot)
│   │   │   ├── binance.py # BinanceClient (python-binance)
│   │   │   └── router.py  # Selección de exchange
│   │   └── forex/
│   │       ├── mt5_bridge.py  # MT5 Python API bridge
│   │       └── strategies/    # HFT XAUUSD, ICT/FVG migrados
│   └── dashboard/
│       ├── api/           # FastAPI — endpoints REST + WebSocket
│       └── frontend/      # React + shadcn/ui + Recharts
├── shared/
│   ├── state.py           # Lector/escritor Redis
│   ├── models.py          # Schemas Pydantic compartidos
│   ├── events.py          # Tipos de mensajes del bus
│   └── config.py          # Config desde .env
├── risk/
│   ├── service.py         # Risk Service independiente
│   └── rules.py           # Reglas globales de drawdown
├── backtesting/
│   ├── engine.py          # Motor de backtesting
│   └── data/              # Datos históricos (de Bot2026/data/)
├── docker-compose.yml
├── .env.example
└── docs/
```

---

## 5. Stack de IA/ML

### 5.1 ML Service — Predicción

**Modelos:**
- `XGBoost / LightGBM` — predicción de dirección en próximas 4 velas (rápido, interpretable, baseline)
- `LSTM / Transformer` — patrones multi-timeframe (M5, M15, H1, H4)
- `Ensemble` — combina ambos con pesos ajustados dinámicamente por régimen de mercado

**Features de entrada:**
- OHLCV multi-TF
- RSI(14), ATR(14), MACD, Bollinger Bands
- Fear & Greed Index
- Sentiment de noticias (score 0-1)
- Hora del día, día de semana (sesiones forex)

**Pipeline de reentrenamiento:**
1. Trigger automático cada 7 días con datos nuevos
2. Validación: Sharpe Ratio > 1.0 en últimas 2 semanas out-of-sample
3. Si pasa → promueve a producción vía MLflow Model Registry
4. Si falla → mantiene versión anterior, genera alerta

### 5.2 RL Service — Aprendizaje Autónomo

**Framework:** Stable-Baselines3 (PPO y SAC)  
**Entorno:** Gym personalizado con datos OHLCV reales y fees reales  
**Función de recompensa:**
```
reward = sharpe_ratio_diario
       - 0.5 * max(0, drawdown - 0.03)   # penaliza drawdown > 3%
       - 0.1 * n_trades_excesivos          # penaliza overtrading
```

**Fases de promoción:**
| Fase | Condición de entrada | Condición de salida |
|---|---|---|
| 1. Simulación | Siempre | Sharpe > 1.2 en 6 meses simulados |
| 2. Paper trading | Supera Fase 1 | Sharpe > 1.0 en 2 semanas real |
| 3. Live mínimo | Supera Fase 2 | Capital ≤ $100, 4 semanas positivas |
| 4. Autonomía completa | Supera Fase 3 | Sin límite de capital |

### 5.3 Orchestrator — LLM Decision Engine

**Modelo primario:** Claude Haiku (bajo costo, rápido)  
**Fallback:** Gemini 2.0 Flash (gratuito)  
**Fallback final:** Reglas deterministas locales (sin API)

**Contexto que recibe cada ciclo (15 min):**
- Precios y tendencias BTC, ETH, XAUUSD
- ATR%, régimen de volatilidad
- Señales activas de ML (con confianza %)
- Estado del agente RL (fase actual)
- Drawdown actual, exposición total
- Próximos eventos macro (calendario económico)

**Decisiones posibles:**
```python
{
  "action": "HOLD|BUY|SELL|ADJUST_POSITION|PAUSE_STRATEGY|RESUME_ALL|STOP_ALL",
  "market": "crypto|forex|both",
  "exchange": "bitget|binance|mt5|auto",
  "strategy": "grid|rsi|ml|rl|technical",
  "capital_pct": 0.0-1.0,
  "reason": "string (max 2 oraciones)",
  "confidence": 0.0-1.0
}
```

---

## 6. Gestión de Riesgo Global

Aplica a todos los ejecutores simultáneamente:

```
Drawdown diario > 2%  → Pausa RL y ML (mayor riesgo), solo técnicas
Drawdown diario > 4%  → Solo Grid Bot (más conservador)
Drawdown diario > 6%  → STOP ALL + alerta Telegram inmediata

Correlación Crypto-Forex > 0.8  → Reducir exposición en Forex 50%

Evento macro detectado (NFP, CPI, FOMC):
  → Pausa Forex 30 min antes y 30 min después
  → Mantiene Crypto si volatilidad < umbral

Horario:
  → Crypto: 24/7
  → Forex: evita 00:00-02:00 GMT (baja liquidez)
  → XAUUSD: pausa durante cierre de NY (21:00-23:00 GMT)
```

**Capital Allocation:**
```
Capital Total
├── 50% Crypto
│   ├── 50% Bitget  (Grid ETH, RSI)
│   └── 50% Binance (BTC, ML signals)
├── 40% Forex/MT5
│   ├── 60% XAUUSD HFT + ICT
│   └── 40% Forex majors (ML H1/H4)
└── 10% Reserva siempre líquida
```

---

## 7. Dashboard

**Backend:** FastAPI con WebSocket para updates en tiempo real  
**Frontend:** React + shadcn/ui + Recharts (gráficas de P&L)  
**Notificaciones:** Bot de Telegram

**Pantallas:**
| Ruta | Contenido |
|---|---|
| `/` | P&L total en tiempo real, Crypto vs Forex |
| `/strategies` | Estado de cada bot: activo/pausado/P&L individual |
| `/ml` | Accuracy de modelos, últimas predicciones, Sharpe por modelo |
| `/rl` | Fase actual del agente RL, métricas de entrenamiento |
| `/risk` | Drawdown actual, exposición, alertas activas |
| `/backtest` | UI para lanzar backtests con parámetros personalizados |
| `/logs` | Historial de decisiones del Orquestador con reasoning |

**Alertas Telegram:**
- Fill ejecutado (compra/venta)
- Drawdown supera umbral
- Modelo ML promovido a producción
- STOP ALL activado
- P&L diario (resumen a las 23:00 UTC)

---

## 8. Autonomía Adaptativa

| Tipo de estrategia | Nivel de autonomía | Condición de cambio |
|---|---|---|
| Grid Bot, RSI Bot técnico | Totalmente autónomo desde día 1 | — |
| ML predictivo | Semi-autónomo hasta validación | Sharpe > 1.0 en 2 semanas |
| RL Agent | 4 fases de promoción progresiva | Ver sección 5.2 |
| Eventos macro extremos | Siempre semi-autónomo | NFP, crisis, black swan |

---

## 9. Agentes y Skills para Construcción

| Componente | Agente Claude Code | Skills |
|---|---|---|
| Data Service | `Data Engineer` | `python-pro`, `async-python-patterns` |
| ML Service | `ML Developer` | `ml-engineer`, `scikit-learn`, `mlops-mlflow` |
| RL Service | `AI Engineer` | `stable-baselines3`, `reinforcement-learning` |
| Orchestrator | `AI Engineer` | `llm-app-patterns`, `agent-development` |
| Executor Crypto | `Backend Architect` | `python-pro`, `api-integration-specialist` |
| Executor Forex | `Backend Architect` | `mql5-master-expert`, `python-pro` |
| Risk Service | `Backend Dev` | `risk-metrics-calculation` |
| Dashboard API | `Backend Dev` | `fastapi-pro` |
| Dashboard UI | `Frontend Developer` | `react-dev`, `shadcn`, `shadcn-ui-blocks` |
| Alertas Telegram | `DevOps Automator` | `telegram-bot-builder` |
| Infra Docker | `DevOps Automator` | `docker-compose-prod-grade` |
| Tests | `Tester` | `python-testing-patterns`, `tdd` |

**Workflow de desarrollo:**
1. `Backend Architect` diseña interfaces entre servicios
2. Cada servicio construido por su agente especializado en paralelo
3. `Tester` escribe tests de integración entre servicios
4. `DevOps Automator` configura Docker Compose y CI/CD
5. `Frontend Developer` construye dashboard con datos reales

---

## 10. Plan de Fases de Implementación

### Fase 1 — Fundamentos (Semana 1-2)
- [ ] Estructura del proyecto y Docker Compose
- [ ] Redis Message Bus + schemas compartidos
- [ ] Data Service (feeds Bitget + Binance WebSocket)
- [ ] Executor Crypto básico (Bitget + Binance sin ML)
- [ ] Risk Service con reglas básicas
- [ ] Dashboard mínimo (P&L + estado)

### Fase 2 — ML/IA (Semana 3-4)
- [ ] ML Service con XGBoost (baseline rápido)
- [ ] Integración ML → Orchestrator → Executor
- [ ] LSTM training pipeline con datos históricos
- [ ] MLflow tracking
- [ ] Alertas Telegram

### Fase 3 — Forex + RL (Semana 5-6)
- [ ] MT5 Python Bridge
- [ ] Executor Forex con estrategias HFT XAUUSD
- [ ] RL Service Fase 1 (simulación)
- [ ] Backtesting engine con UI

### Fase 4 — Producción (Semana 7-8)
- [ ] Hardening de risk management
- [ ] RL paper trading (Fase 2)
- [ ] Dashboard completo con todas las pantallas
- [ ] Despliegue en VPS
- [ ] Monitoring y alertas completas

---

## 11. Criterios de Éxito

- Sistema corre 24/7 sin intervención manual en estrategias técnicas
- ML models con Sharpe > 1.0 sostenido 2+ semanas antes de autonomía
- Dashboard muestra estado real con latencia < 2 segundos
- STOP ALL se activa correctamente ante drawdown > 6%
- Binance y Bitget ejecutan órdenes correctamente con gestión de fees
- MT5 bridge ejecuta en XAUUSD sin desconexiones

---

*Spec generado mediante brainstorming con Claude Code — 2026-06-20*  
*Proyecto: H:\Dev-Drive\AlgoCore (por crear)*
