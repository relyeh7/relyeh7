# Zone Indicators — MTF Buy/Sell Signal Arrows — Diseño

Fecha: 2026-09-23
Estado: Aprobado por el usuario (diseño conversacional, secciones 1-2)
Depende de: `2026-09-22-zone-indicators-suite-design.md` (los 3 indicadores base ya
construidos y desplegados — SMC_ZonesInd, CRT_ZonesInd, VWAP_ZonesInd)

## 1. Objetivo

Agregar, a cada uno de los 3 indicadores existentes (por separado, cada uno con su
propia fila — opción elegida por el usuario sobre un panel de confluencia unificado),
una fila nueva en su panel interactivo que muestra, para 6 temporalidades
(M1/M5/M15/H1/H4/D1), una flecha de color indicando si esa temporalidad tiene
actualmente una señal de compra (verde) o venta (roja) según la propia lógica de
detección de ese indicador.

No se agrega lógica de detección nueva — se reutiliza el motor de cada indicador
(`CSMCZonesEngine`, `CCRTZonesEngine`, `CVWAPZonesEngine`) tal cual, alimentándolo con
velas de otras temporalidades.

## 2. Alcance

- Aplica a los 3 indicadores por igual, cada uno de forma independiente (mismo
  patrón, sin componente compartido nuevo en `Common/` — sigue el precedente ya
  establecido de no compartir lógica de motor entre indicadores).
- 6 temporalidades fijas: M1, M5, M15, H1, H4, D1 (mismo set que el dashboard MTF ya
  existente en `SMC/SMC_Indicator.mq5`, para consistencia con el repo).
- Señal por temporalidad: existe una zona activa (no mitigada) en esa dirección;
  prioridad a zonas A+ (mayor fuerza/confluencia) sobre zonas normales si ambas
  coexisten. Sin zona activa en ninguna dirección = sin flecha (celda gris/vacía).
- Sin handles de indicador — cada escaneo por temporalidad usa `CopyRates()` +
  una instancia temporal del motor ya existente, igual que el enfoque sin-handles
  que ya usa VWAP_ZonesInd.
- Refresco en `OnTimer` (no en cada tick ni en `OnCalculate`), configurable via
  `InpMTFRefreshSeconds` (default 10s). La temporalidad del gráfico actual no se
  re-escanea — se reusa el resultado que el indicador ya calcula en `OnCalculate`.
- Lookback configurable por temporalidad, `InpMTFLookbackBars` (default 300).
- Toggle en el panel para mostrar/ocultar la fila MTF, independiente de las demás
  capas.
- Sin alertas nuevas asociadas a cambios de señal MTF — solo visual en esta
  iteración.

## 3. Estructura de archivos (por indicador, patrón idéntico ×3)

```
ZoneIndicators/MQL5/Include/SMC_ZonesInd/
├── SMC_ZonesEngine.mqh   (sin cambios)
├── SMC_ZonesPanel.mqh    (modificado: fila MTF + toggle)
└── SMC_ZonesMTF.mqh      (NUEVO: escaneo MTF, motor reutilizado)
```

(Análogo para `CRT_ZonesInd` y `VWAP_ZonesInd`.)

`*_ZonesMTF.mqh` expone algo como:

```mql5
enum ENUM_ZI_MTF_SIGNAL { ZI_MTF_NONE, ZI_MTF_BUY, ZI_MTF_SELL };

class CSMCZonesMTFScanner
{
public:
   void ScanAll(const string symbol, const int lookback_bars);
   ENUM_ZI_MTF_SIGNAL Signal(const int tf_index) const; // 0..5 = M1..D1
};
```

`ScanAll()` hace, para cada una de las 6 temporalidades: `CopyRates()`, instancia un
`CSMCZonesEngine` temporal (misma clase que usa el indicador principal, sin
modificar), le hace procesar las velas copiadas bar por bar (mismo bucle que
`OnCalculate` ya usa), y al terminar consulta la zona activa más reciente en cada
dirección para decidir `ZI_MTF_BUY`/`ZI_MTF_SELL`/`ZI_MTF_NONE` (prioridad A+ sobre
normal, según reglas de §2).

## 4. Integración con el indicador principal

- `OnTimer()` (nuevo, o extendido si ya existe): cada `InpMTFRefreshSeconds`
  segundos, llama `g_mtf_scanner.ScanAll(_Symbol, InpMTFLookbackBars)`.
- El panel lee `g_mtf_scanner.Signal(i)` para las 6 celdas y las redibuja al
  refrescar (mismo patrón de redibujado que el resto del panel).
- `OnCalculate()` no cambia — el escaneo MTF es completamente independiente de la
  detección del gráfico actual.

## 5. Panel — fila MTF

Nueva sección "MTF SIGNALS" debajo de los controles existentes de cada panel:
6 celdas etiquetadas M1/M5/M15/H1/H4/D1, cada una mostrando una flecha/indicador de
color (verde=compra, rojo=venta, gris=sin señal). Checkbox independiente
"Show MTF Row" que oculta/muestra toda la fila sin afectar las demás capas.

## 6. Testing

Cada `*_TestRunner.mq5` (EA) gana asserts nuevos:
- Clasificación correcta de señal (COMPRA/VENTA/SIN SEÑAL) alimentando velas
  sintéticas de una temporalidad ficticia al escáner.
- Prioridad A+ sobre zona normal cuando ambas coexisten en la misma dirección.
- El refresco respeta `InpMTFRefreshSeconds` (no reescanea antes de tiempo).

Meta: 0 errores/0 warnings + suite de asserts en verde, igual que el resto de la
suite, antes de desplegar.

## 7. Despliegue

Mismo flujo ya establecido: `tools\build.ps1` (compila los 6 targets existentes,
ahora con los 3 archivos `*_ZonesMTF.mqh` nuevos incluidos) → `tools\deploy.ps1` a
demo D4CE. Despliegue a D0E8 (real) solo si el usuario lo pide explícitamente de
nuevo, igual que la suite base.

## 8. Fuera de alcance

- No hay panel de confluencia unificado entre los 3 indicadores (opción descartada
  por el usuario a favor de 3 filas independientes).
- No hay alertas por cambio de señal MTF en esta iteración.
- No se agregan más de 6 temporalidades ni se hacen configurables cuáles son.
