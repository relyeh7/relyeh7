# Zone Indicators Suite — Diseño

Fecha: 2026-09-22
Estado: Aprobado por el usuario (diseño conversacional, secciones 1-3)

## 1. Objetivo

Construir tres indicadores MQL5 independientes, cada uno detectando zonas de
COMPRA y VENTA (bidireccional) mediante una metodología distinta, aprovechando
el corpus MQL5 ya minado (documentación oficial, MQL5Book, artículos
verificados por compilación en `mql5-article-miner`) en vez de reutilizar
código de proyectos previos (`4 Types of Sell Zones/`, `SMC/`).

Los tres son módulos de detección/visualización — no Expert Advisors, no
ejecutan órdenes.

## 2. Alcance

- Genérico: cualquier símbolo, cualquier timeframe.
- Cada indicador construido desde cero, aislado de `4 Types of Sell Zones/`
  y `SMC/` (sin dependencias de esos motores).
- Panel interactivo completo (CAppDialog) en los 3, siguiendo el patrón ya
  validado en `SMC_Indicator.mq5` / `GridFib_Indicator.mq5`.
- Alertas push/sonido en los 3.
- Despliegue final solo a terminal demo D4CE (nunca D0E8 sin pedido explícito
  posterior).

## 3. Estructura de carpetas

```
H:\Dev-Drive\ZoneIndicators\
├── Common\
│   └── ZI_Common.mqh
├── SMC_ZonesInd\
│   ├── SMC_ZonesInd.mq5
│   ├── SMC_ZonesEngine.mqh
│   ├── SMC_ZonesPanel.mqh
│   └── Tests\SMC_ZonesInd_TestRunner.mq5
├── CRT_ZonesInd\
│   ├── CRT_ZonesInd.mq5
│   ├── CRT_ZonesEngine.mqh
│   ├── CRT_ZonesPanel.mqh
│   └── Tests\CRT_ZonesInd_TestRunner.mq5
├── VWAP_ZonesInd\
│   ├── VWAP_ZonesInd.mq5
│   ├── VWAP_ZonesEngine.mqh
│   ├── VWAP_ZonesPanel.mqh
│   └── Tests\VWAP_ZonesInd_TestRunner.mq5
├── tools\ (build.ps1, deploy.ps1, compile.ps1 — extendidos del patrón GridFib)
└── docs\ (spec, plan, reports)
```

`ZI_Common.mqh` es la única pieza compartida entre los 3:
- `struct ZI_Zone { double price_hi, price_lo; ENUM_ZI_TYPE type /*BUY|SELL*/;
  int strength; datetime bar_time; bool mitigated; string label; }`
- `ZI_Alert(...)` — helper de `Alert()` + `SendNotification()` con throttling
  por barra.
- Helper de conversión de color a BGR para el panel (necesario solo si se
  persiste a `.tpl`; los `input color` del indicador no lo requieren).

Ningún motor de detección (`*_Engine.mqh`) comparte código entre sí ni con
proyectos previos.

## 4. Metodología por indicador

### 4.1 SMC_ZonesInd — Smart Money Concepts bidireccional

Extiende el concepto de "4 Types of Sell Zones" (documentado en
`4 Types of Sell Zones/SMC_4_Tipos_de_Zonas_de_Venta.md`) a ambas direcciones,
calculado desde cero:

| Zona de VENTA | Zona de COMPRA (espejo) |
|---|---|
| Supply OB: última vela antes de impulso bajista ≥3× su cuerpo | Demand OB: última vela antes de impulso alcista ≥3× su cuerpo |
| Bearish FVG: gap de 3 velas bajando (Low vela1 → High vela3) | Bullish FVG: gap de 3 velas subiendo (High vela1 → Low vela3) |
| Equal Highs (BSL) + wick sweep + cierre por debajo | Equal Lows (SSL) + wick sweep + cierre por encima |
| Premium (>50% EQ del rango) = filtro de venta | Discount (<50% EQ del rango) = filtro de compra |

**Confluencia:** cada zona activa acumula `strength` +1 por cada zona
superpuesta (stacking); ≥2 = señal A+, resaltada en panel + alerta
diferenciada. Zona se invalida (`mitigated=true`, se borra) cuando el precio
cierra a través de toda la zona sin reversión.

### 4.2 CRT_ZonesInd — Candle Range Theory

Basado en el material CRT ya transcrito (`project_candle_range_theory` en
memoria / prompt maestro M01-M18):
- **Rango de referencia:** high/low de sesión o vela anterior (input:
  Daily/4H/Session).
- **Fase de manipulación:** sweep (wick) por encima/debajo del rango de
  referencia.
- **Fase de distribución/confirmación:** cierre de reingreso dentro del rango
  tras el sweep → esa vela marca la zona.
- **Zona de COMPRA:** sweep bajo el low del rango + cierre de reingreso
  alcista.
- **Zona de VENTA:** sweep sobre el high del rango + cierre de reingreso
  bajista.
- **Filtro de fuerza:** el sweep debe superar un mínimo de puntos/ATR (input)
  para descartar ruido de spread.

### 4.3 VWAP_ZonesInd — VWAP + bandas de desviación con agotamiento de volumen

- **Ancla:** VWAP de sesión (reset diario) + bandas ±1σ/±2σ (inputs).
- **Zona de COMPRA:** toque de banda inferior (1σ o 2σ, input) + volumen del
  toque < promedio móvil de volumen de N barras (agotamiento vendedor).
- **Zona de VENTA:** toque de banda superior + volumen decreciente
  (agotamiento comprador).
- **Nota de dato:** usa `VOLUME_TICK` por defecto (tick volume); no todos los
  símbolos/brokers proveen `VOLUME_REAL` fiable — documentar el fallback en
  el código.

## 5. Flujo de datos (común a los 3)

`OnCalculate` procesa solo barras nuevas → el motor evalúa su condición sobre
`CopyRates`/`CopyBuffer` (con validación de retorno ≥0) → si detecta zona,
crea un `ZI_Zone` y lo agrega a un array dinámico → el `.mq5` principal dibuja
`OBJ_RECTANGLE` (zona) + `OBJ_TEXT` (etiqueta tipo/fuerza) → en cada tick se
revisa si alguna zona activa fue mitigada (precio cerró a través) y se
remueve.

## 6. Panel (CAppDialog — mismo layout en los 3)

- Checkboxes para mostrar/ocultar cada sub-tipo de zona (ej. en SMC:
  OB/FVG/Sweep/Premium-Discount por separado).
- Input/slider de fuerza mínima de confluencia para resaltar.
- Toggle de alertas (push/sonido) independiente del toggle visual.
- Panel arrastrable con anclaje a esquina (patrón "corner anchoring" de SMC).

## 7. Alertas

Vía `ZI_Alert()` común: dispara `Alert()` + `SendNotification()` (si push
habilitado) al **formarse** una zona nueva y, opcionalmente, al **tocarse**
una zona existente (input separado). Throttling: no repetir la misma alerta
en la misma barra.

## 8. Manejo de errores (lecciones ya registradas en memoria)

- Handles de indicador (ej. `iMA`/`iStdDev` internos de VWAP) se crean una
  sola vez en `OnInit`, nunca por tick — evita el fallo silencioso de
  `BarsCalculated < 1` ya documentado (memoria: indicator-handle, ea-builder,
  trailing, bug-fix).
- Validación `INVALID_HANDLE` tras cada creación de handle.
- Guardas en cada `CopyBuffer`/`CopyRates` antes de indexar arrays (memoria:
  session-filter, copybuffer, bug-fix).

## 9. Testing

Cada indicador lleva su `TestRunner.mq5` (patrón GridFib_TestRunner) ejecutado
headless en el Strategy Tester, con asserts sobre:
- Detección correcta en barras sintéticas/históricas conocidas.
- Mitigación/eliminación de zona.
- Toggle del panel afectando visibilidad.
- Disparo de condición de alerta.

Meta: 0 errores/0 warnings de compilación + suite de asserts en verde antes
de desplegar.

## 10. Despliegue

Compilación vía `tools\build.ps1` → deploy solo a terminal demo D4CE vía
`tools\deploy.ps1` (extendiendo el patrón GridFib/SMC). D0E8 explícitamente
excluido salvo pedido posterior del usuario.

## 11. Fuera de alcance

- No se modifica ni depende de `4 Types of Sell Zones/` ni `SMC/`.
- No hay ejecución de órdenes (no son EAs).
- No hay integración con NT8 (C#) — solo MQL5/MT5.
- No hay despliegue a terminal real D0E8 en este proyecto.
