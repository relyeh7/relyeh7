# Patrones minados/confirmados — SMC, CRT, VWAP (Task 2)

Fuente: `H:\Dev-Drive\MQL5_Articles\` (corpus local de mql5.com/es/articles, veredictos de compilacion
de `compile_all.py` / `articles.py code --ok`, arbol de build aislado con Standard Library pristina).
Todo lo marcado **OK** abajo fue confirmado con `articles.py code "<patron>" --ok` contra el indice
`index/code_index.json`, no asumido. Ningun indicador final fue construido aqui — solo se aisla el
patron para que Tasks 3-5 (MQL5 Indicator Builder) lo adapten.

---

## 1. SMC bidireccional: Order Blocks + Fair Value Gaps + liquidity sweep

No habia entrada previa en `series_catalog.md` para esta combinacion — minado fresco.

### 1a. Order Blocks

- **Articulo:** [15899](https://www.mql5.com/es/articles/15899) — Niquel Mendoza, *"Desarrollo de Sistemas
  Avanzados de Trading ICT: Implementacion de Order Blocks en un Indicador"* (2024-10-30).
- **Adjunto:** `attachments/15899/Order_Block_Indicator_New.mq5` (967 lineas, tipo Indicators).
  Compilado **OK** (`articles.py code "OrderBlock" --kind Indicators --ok`). La serie continua con
  `Order_Block_Indicador_New_Part_2.mq5` en los ids 16268, 17640, 17957, 18111 (anade `OnBookEvent`
  para el libro de ordenes) — las cuatro variantes tambien compilan **OK**; 15899 es la base sin DOM,
  mas simple de adaptar a un indicador de zonas puro.
- **Snippet compilado (estructura + deteccion, ya bidireccional):**

```mql5
struct OrderBlock
{
   datetime time1;      // Tiempo de la vela anterior a la primera vela del order block
   double price1;       // Precio superior del order block (nivel 1)
   double price2;       // Precio inferior del order block (nivel 2)
   string name;         // Nombre del order block
   bool mitigated;      // Estado del order block
};

OrderBlocks ob_bajistas[];
OrderBlocks ob_alcistas[];

// Deteccion alcista: 3-4 velas alcistas consecutivas + validacion de mechas/cuerpo
if((esVelaCorrecta_case_normal == true &&
    ((lowArray[two_vela] > ((body1*0.5)+openArray[one_vela]) &&
      ((body2*0.4)+openArray[two_vela]) > highArray[one_vela]) || esVela_Martillo == true)
    && lowArray[tree_vela] > ((body2*0.25)+openArray[two_vela]))
   || fuerte_movimiento_alcista == true || atr_case == true)
{
   int furthestAlcista = FindFurthestAlcista(Time[one_vela], 20);
   // ... asigna price1/price2/time1 a la vela previa al impulso -> newVela_Order_block_alcista
}

// Deteccion bajista: espejo exacto (closeArray < openArray, comparaciones invertidas)
if((esVelaCorrecta_case_normal == true &&
    highArray[two_vela] < ((body1*0.70)+closeArray[one_vela]) &&
    ((body2*0.4)+closeArray[two_vela]) < lowArray[one_vela] &&
    highArray[tree_vela] < highArray[two_vela])
   || a == true || fuerte_movimiento_bajista == true)
{
   int furthestBajista = FindFurthestBajista(Time[one_vela], 20);
   // ... asigna newVela_Order_Block_bajista
}

// Mitigacion (recorre velas posteriores al OB buscando cierre/mecha dentro de la zona)
datetime esOb_mitigado_array_alcista(OrderBlocks &newblock, datetime end)
{
   for(int i = 0; i < endIndex-2; i++)
      if((newblock.price2 >= low || newblock.price2 >= open) || newblock.price2 >= close)
      { newblock.mitigated = true; return iTime(_Symbol,PERIOD_CURRENT,i); }
   return 0;
}
```

- **Ya es bidireccional de origen** (arrays `ob_alcistas[]`/`ob_bajistas[]`, funciones espejo
  `FindFurthestAlcista`/`FindFurthestBajista`, `esOb_mitigado_array_alcista`/`_bajista`). No hace
  falta invertir logica — solo:
  1. Extraer solo `struct OrderBlock` + las 4 funciones de deteccion/mitigacion, no el resto del
     articulo (colores, inputs de dibujo del autor).
  2. Renombrar a ingles/estilo del proyecto (`ob_bullish[]`/`ob_bearish[]`) por la convencion "sin `ñ`"
     de `mql5-hft-quant-developer`.
  3. Sustituir el ATR propio (`atr_i = iATR(_Symbol,PERIOD_CURRENT,14)`) por el handle compartido si
     `ZI_Common.mqh` ya expone uno (evitar duplicar el handle entre los 3 indicadores del suite).
  4. El array `ob_alcistas`/`ob_bajistas` crece sin limite — anadir poda por antiguedad o por
     `mitigated == true` antes de usarlo en produccion (el articulo no lo hace).

### 1b. Fair Value Gaps (FVG)

- **Articulo:** [18669](https://www.mql5.com/es/articles/18669) — Eugene Mmene, *"Dominar los Fair
  Value Gaps: formacion, logica y automatizacion"*.
- **Adjunto:** `attachments/18669/Fvg_detector.mq5` (121 lineas, Experts). Compilado **OK**
  (`articles.py code "FVG" --ok`).
- **Snippet compilado (deteccion de 3 velas, ya bidireccional):**

```mql5
double low0  = iLow(eaSymbol, tfs[i].tf, 0);
double high2 = iHigh(eaSymbol, tfs[i].tf, 2);
double gap_L0_H2 = NormalizeDouble((low0 - high2) / _Point, 0);   // hueco alcista

double high0 = iHigh(eaSymbol, tfs[i].tf, 0);
double low2  = iLow(eaSymbol, tfs[i].tf, 2);
double gap_H0_L2 = NormalizeDouble((low2 - high0) / _Point, 0);  // hueco bajista

if(gap_L0_H2 > minPts)   // FVG alcista: low[0] > high[2]
   CreateRec(fvgName, iTime(...,0), high2, iTime(...,0)+PeriodSeconds(tf)*FVG_Rec_Ext_Bars, low0, CLR_UP);

if(gap_H0_L2 > minPts)   // FVG bajista: high[0] < low[2]
   CreateRec(fvgName, iTime(...,0), low2, iTime(...,0)+PeriodSeconds(tf)*FVG_Rec_Ext_Bars, high0, CLR_DOWN);
```

- Ya multi-timeframe (`TimeframeData tfs[]`) y ya bidireccional. Adaptacion necesaria:
  1. Es un EA (`OnTick`/`OnDeinit`); portar `DetectFVGs()` a `OnCalculate()` de un indicador
     (reemplazar el `NewBar()` manual por el patron `prev_calculated` estandar).
  2. `minPts` (100 puntos) es un umbral fijo — para XAUUSD/indices conviene normalizar a ATR o a
     `_Point`-adjusted por simbolo, el articulo no lo hace (queda fijo en puntos brutos).
  3. Alternativas ya compiladas si se necesita algo mas completo: 16659
     `IFVG-Example-Code.mq5` (308 lineas, incluye deteccion de FVG **invertido** — cuando el precio
     rompe un FVG y este cambia de rol soporte/resistencia) y 14261 `FVG_SMC_EA.mq5` (518 lineas,
     combina FVG con estructura SMC completa) — ambos **OK**, mayor complejidad si se quiere IFVG.

### 1c. Liquidity sweep (barrido de maximos/minimos)

- **Articulo:** [18379](https://www.mql5.com/es/articles/18379) — lynnchris, *"Liquidity Sweep with
  MA filter"* (parte del kit de herramientas de accion del precio).
- **Adjunto:** `attachments/18379/Liquidity_Sweep.mq5` (285 lineas, Experts). Compilado **OK**.
- **Snippet compilado (deteccion bidireccional con dos niveles de estrictez):**

```mql5
bool bullSweep, bearSweep;
if(SignalStrict == LessStrict)
{
   bullSweep = (c > o && l < l1 && c > o1  && c1 != o1);   // mecha rompe low anterior, cierra dentro/arriba
   bearSweep = (c < o && h > h1 && c < o1  && c1 != o1);
}
else // Strict
{
   bullSweep = (c > o && l < l1 && c > h1 && c1 != o1);    // cierre supera el high de la vela barrida
   bearSweep = (c < o && h > h1 && c < l1 && c1 != o1);
}
```

- **Limitacion honesta:** esto es un barrido de **un solo maximo/minimo anterior** (vela `shift+1`),
  no de un **pool de maximos/minimos iguales** (equal highs/lows) acumulados en una ventana — no existe
  en el corpus ningun articulo que implemente deteccion de EQH/EQL como tal (busquedas por
  `EqualHigh|EqualLow|EQH|EQL` devolvieron 0 coincidencias). La adaptacion bidireccional para el
  indicador final debe:
  1. Mantener la logica bull/bear de arriba tal cual para el "sweep" puntual (ya probada).
  2. Anadir, como capa nueva (sin precedente en el corpus, logica simple a escribir directamente):
     agrupar swing highs/lows dentro de una tolerancia en puntos/ATR sobre una ventana de N barras
     para marcar el "pool de liquidez", y disparar la senal cuando el sweep puntual (arriba) ocurre
     sobre uno de esos niveles agrupados en vez de sobre cualquier maximo/minimo suelto.
  3. El filtro de MA (`UseMAFilter`, con VWMA/HMA propios) es opcional y reciclable tal cual si el
     indicador quiere confirmar direccion de tendencia antes de marcar el sweep.

---

## 2. CRT — sweep de rango de sesion con reingreso

**Ya curado en `series_catalog.md`** (linea 136, curacion 2026-09-22) — no hizo falta minar de nuevo:

> 18911 (Christian Benjamin, "Kit de herramientas para el analisis de la accion del precio" Parte 33)
> — `CandleRangeTheory.mqh::CRangePattern` — motor CRT ya identificado en
> `[[project-candle-range-theory]]`; confirmado como **unico match compilado 0/0 en todo el corpus**
> para la clase `CRangePattern`, es la referencia canonica, no hay alternativa que comparar.

- **Articulo:** [18911](https://www.mql5.com/es/articles/18911) — *"Desarrollo de un kit de
  herramientas para el analisis de la accion del precio (Parte 33): Candle Range Theory"*.
- **Adjunto:** `attachments/18911/CandleRangeTheory.mqh` — clase `CRangePattern`. Confirmado **OK**
  (verificado de nuevo en esta tarea: `articles.py code "CRangePattern" --ok` -> 1 coincidencia,
  unica en todo el corpus).
- **Nota de contexto:** existe ademas `[[project-candle-range-theory]]` (memoria del proyecto) — un
  libro CRT transcrito completo + prompt maestro modular M01-M18 para MT5/NT8/TradingView, ya
  disponible como referencia complementaria mas alla de este unico articulo si Task 4 necesita
  profundidad teorica adicional sobre manipulacion/distribucion de sesion.
- **Adaptacion bidireccional:** la clase ya modela sweep+reentry por diseno (rango de sesion, ruptura
  falsa hacia un lado, reingreso hacia el lado contrario) — es simetrica por construccion, revisar
  solo que los parametros de sesion (horario) se configuren para ambos lados (Asia/Londres/NY) sin
  sesgo direccional fijo.

---

## 3. VWAP de sesion + bandas de desviacion estandar + agotamiento de volumen

No habia entrada previa en `series_catalog.md`. Minado en tres piezas porque **no existe en el
corpus un articulo que combine las tres cosas en una sola clase** — se documenta cada pieza por
separado con su propio veredicto de compilacion, y se es explicito sobre lo que no esta probado.

### 3a. VWAP de sesion (linea central) — OK, listo para reusar

- **Articulo:** [10329](https://www.mql5.com/es/articles/10329) — Daniel Jose, *"Indicador VWAP
  (IntraDay)"* (serie "Examples").
- **Adjunto:** `attachments/10329/Examples___VWAP/Indicators/VWAP.mq5` (52 lineas). Compilado **OK**.
- **Snippet compilado completo (session-reset + prev_calculated correcto):**

```mql5
#define macroGetDate(A) (A - (A % 86400))
double VWAP_Buff[];

int OnCalculate(const int rates_total, const int prev_calculated,
                const datetime &time[], const double &open[], const double &high[],
                const double &low[], const double &close[],
                const long &tick_volume[], const long &volume[], const int &spread[])
{
   double Price = 0; ulong Volume = 0;
   static int siPos = 0;

   if(macroGetDate(time[rates_total-1]) != macroGetDate(time[siPos]))   // nueva sesion
   {
      for(int c0 = rates_total-1; macroGetDate(time[siPos]) != macroGetDate(time[c0]); siPos++);
      ArrayInitialize(VWAP_Buff, EMPTY_VALUE);
   }
   for(int c0 = siPos; c0 < rates_total; c0++)
   {
      Price += ((high[c0]+low[c0]+close[c0])/3) * volume[c0];
      Volume += volume[c0];
      VWAP_Buff[c0] = Price / Volume;
   }
   return rates_total;
}
```

- Nota: usa `volume[]` (real volume del broker), no `tick_volume[]` — en simbolos/brokers sin volumen
  real esto queda en 0 y el VWAP se rompe; para XAUUSD/FX conviene cambiar a `tick_volume[]` al
  adaptarlo (cambio trivial, una palabra).
- **Descartado como base:** id 17934 `VWAP.mqh::CVWAP` (Include, 460 lineas, tambien **OK**) — es un
  **algoritmo de ejecucion de ordenes** (parte de "TWAP, VWAP y ordenes Iceberg") que trocea una orden
  grande en el tiempo siguiendo un perfil de volumen historico; no calcula un VWAP de sesion como
  nivel de precio para el grafico. No sirve para un indicador de zonas, se descarta explicitamente
  para que Task 3-5 no lo confunda con el patron correcto.
- **Descartado tambien:** id 16984 `VWAP.mq5` (Experts, "Flujo externo (II) VWAP" — misma serie que dio
  el CRT canonico) — delega el calculo completo del VWAP a un servidor Python externo por
  `WebRequest`, no hay matematica de VWAP en MQL5 dentro del adjunto; util solo como referencia de
  arquitectura, no como fuente del calculo.

### 3b. Bandas de desviacion estandar (tecnica de construccion) — OK, requiere adaptacion

- **Articulo:** [130](https://www.mql5.com/es/articles/130) — Sergey Greecie, *"Standard Deviation
  Channel"* (indicador clasico del catalogo base de ejemplos).
- **Adjunto:** `attachments/130/indicators/indicators/Indicators/StandardDeviationChannel.mq5`
  (119 lineas). Compilado **OK** (`articles.py code "iStdDev" --kind Indicators --ok`).
- **Snippet compilado (la parte reutilizable: banda = centro ± k·StdDev via handle nativo):**

```mql5
ExtMAHandle      = iMA(NULL,0,InpMAPeriod,0,InpMAMethod,InpAppliedPrice);
ExtStdDevMAHandle= iStdDev(NULL,0,InpMAPeriod,0,InpMAMethod,InpAppliedPrice);
...
CopyBuffer(ExtMAHandle,0,0,to_copy,ExtMABuffer);
CopyBuffer(ExtStdDevMAHandle,0,0,to_copy,ExtStdDevBuffer);

for(int i=limit; i<rates_total; i++)
{
   ExtMiddBuffer[i] = ExtMABuffer[i];
   ExtUpBuffer[i]   = ExtMABuffer[i] + (InpDeviation*ExtStdDevBuffer[i]);
   ExtDownBuffer[i] = ExtMABuffer[i] - (InpDeviation*ExtStdDevBuffer[i]);
}
```

- **Adaptacion necesaria (no probada como combinacion, solo la tecnica esta probada):** este articulo
  calcula StdDev **alrededor de una media movil estandar** (`iStdDev` nativo), no alrededor del VWAP.
  Para bandas de VWAP verdaderas hay dos caminos, ninguno con precedente compilado en el corpus:
  1. **Aproximacion rapida** (la que usa la mayoria de implementaciones de VWAP bands en la practica):
     reusar el handle `iStdDev` tal cual sobre el mismo precio aplicado del VWAP (ej. `PRICE_TYPICAL`)
     y sumar/restar `k*StdDev` a la linea VWAP de 3a en vez de a la media movil. Riesgo: el StdDev
     nativo no esta ponderado por volumen, solo aproxima.
  2. **Version exacta** (mas fiel a "VWAP bands" real): acumular `Sum(volume*(typical_price-VWAP)^2)`
     dentro del mismo bucle de sesion de 3a y sacar la raiz cuadrada ponderada — es aritmetica simple
     de anadir al bucle existente, no requiere mineria adicional, pero se debe escribir y compilar
     como parte de Task 3-5, no presentarlo aqui como si viniera ya probado.
  - Recomendacion: usar 2 (exacta) ya que el costo de codigo extra es minimo y evita la ponderacion
    incorrecta de 1.

### 3c. Agotamiento de volumen — SIN precedente rule-based en el corpus (hallazgo honesto)

- Busquedas realizadas sin resultado: `VolumeExhaustion|Volume_Exhaustion|VolumeClimax|climax`,
  `VolumeDivergence|divergencia.*volumen`, `VolumeRatio|LowVolume`, `agotamiento`, `exhaustion`.
- Los dos resultados mas cercanos por tema ("Perspectivas bursatiles a traves del volumen") **si
  compilan OK** pero dependen de una red LSTM/ONNX, no de una regla simple:
  - 16573 `New_Volume_breakout_validation_50.mq5` (233 lineas, `feat: ml`) — OK.
  - 16445 `Volume_high_low_difference_LSTM.mq5` (938 lineas, `feat: ml`) — OK.
  - Ambos son EAs de validacion de rupturas via modelo entrenado, no un detector aritmetico de
    agotamiento; adoptarlos implicaria arrastrar dependencia ONNX solo para esto, desproporcionado
    para un indicador de zonas.
- **Conclusion:** no se fuerza un match debil. Para "deteccion de agotamiento de volumen" en el
  indicador final, la recomendacion es escribir logica simple directamente sobre `tick_volume[]`
  (ej. volumen decreciente durante N barras mientras el precio hace nuevo extremo cerca de una banda
  VWAP) — es aritmetica trivial que no necesita un patron de articulo por separado, pero Task 3-5
  debe saber que **esta pieza especifica no viene de un compilado verificado del corpus**, a
  diferencia de 3a y 3b.

---

## Resumen de citas a usar en el codigo derivado

```
// Basado en mql5.com/es/articles/15899 (Niquel Mendoza) - deteccion/mitigacion de Order Blocks (struct + arrays bull/bear)
// Basado en mql5.com/es/articles/18669 (Eugene Mmene) - deteccion de Fair Value Gap de 3 velas, bidireccional
// Basado en mql5.com/es/articles/18379 (lynnchris) - liquidity sweep de un maximo/minimo previo (bull/bear)
// Basado en mql5.com/es/articles/18911 (Christian Benjamin) - CRangePattern, motor CRT de sweep+reentry de sesion
// Basado en mql5.com/es/articles/10329 (Daniel Jose) - VWAP de sesion con reset diario y prev_calculated
// Basado en mql5.com/es/articles/130 (Sergey Greecie) - tecnica de banda via iStdDev handle (centro +/- k*StdDev), adaptada de MA a VWAP
```
