//+------------------------------------------------------------------+
//| CRT_ZonesMTF.mqh - multi-timeframe buy/sell signal scanner for    |
//| CRT_ZonesInd's panel row. Reuses CCRTZonesEngine as-is (no new    |
//| detection logic) by feeding it CopyRates() bars from 6 fixed      |
//| timeframes through a fresh, throwaway engine instance per scan -  |
//| the same no-handle approach VWAP_ZonesInd uses for its own math.  |
//| Pattern copied from ZoneIndicators\MQL5\Include\SMC_ZonesInd\     |
//| SMC_ZonesMTF.mqh (Task 1), adapted to CCRTZonesEngine's range-    |
//| mode-aware Configure() signature - see the range-mode note on     |
//| Configure()/ScanTimeframe() below.                                |
//+------------------------------------------------------------------+
#ifndef CRT_ZONES_MTF_MQH
#define CRT_ZONES_MTF_MQH

#property strict

#include <ZoneIndicators\ZI_Common.mqh>
#include <CRT_ZonesInd\CRT_ZonesEngine.mqh>

enum ENUM_ZI_MTF_SIGNAL { ZI_MTF_NONE, ZI_MTF_BUY, ZI_MTF_SELL };

//+------------------------------------------------------------------+
//| Pure timing gate mirroring OnTimer()'s once-per-N-seconds         |
//| throttle. Free function (not a class member) so a headless test  |
//| can exercise it without TimeCurrent()/GetTickCount().             |
//+------------------------------------------------------------------+
bool CRT_MTFShouldScan(const datetime lastScanTime, const datetime now, const int intervalSeconds)
{
   if(intervalSeconds <= 0) return true;
   return (now - lastScanTime) >= intervalSeconds;
}

//+------------------------------------------------------------------+
//| CCRTZonesMTFScanner                                               |
//+------------------------------------------------------------------+
class CCRTZonesMTFScanner
{
private:
   ENUM_ZI_MTF_SIGNAL m_signal[6];
   ENUM_TIMEFRAMES    m_tfs[6]; // single source of truth for the 6 tracked timeframes' order/identity,
                                 // shared by ScanAll(), ScanAllReusingCurrent() and IndexForPeriod()

   //--- Detection params, fixed for the scanner's lifetime (see Configure()'s range-mode note).
   ENUM_CRT_RANGE_MODE m_rangeMode;
   int      m_sessionHours[3];
   int      m_atrPeriod;
   bool     m_useATRFilter;
   double   m_minSweepPoints;
   double   m_minSweepATRMult;
   int      m_maxReentryBars;
   double   m_point;
   int      m_minSweepStrength;

   ENUM_ZI_MTF_SIGNAL ScanTimeframe(const string symbol, const ENUM_TIMEFRAMES tf, const int lookback_bars);

public:
                     CCRTZonesMTFScanner(void);

   // rangeMode/sessionHours/atrPeriod/... are captured ONCE here (from the indicator's static
   // Inp* inputs at OnInit) and used identically by all 6 timeframe scans, including the 5
   // non-current throwaway-engine ones - NOT whatever live override the panel's range-mode spin
   // edit (g_range_mode_request -> g_engine.ResetRangeMode()) currently has the main chart's own
   // g_engine set to. Rationale (ruled 2026-09-23, CRT-specific design question from the task
   // brief): the main g_engine's live range-mode override only ever affects the CURRENT
   // timeframe's slot, which ScanAllReusingCurrent() derives directly from g_engine anyway (so it
   // naturally reflects whatever mode the user has live-switched to). The other 5 timeframes have
   // no live engine to reuse - giving them the CURRENT chart's transient override would make an
   // M1 chart's manual "switch to Session mode" click silently change what Daily/H4/etc. count as
   // a signal, which is not what the range-mode selector is for. Each of the 6 scans instead
   // applies the SAME fixed reference-range definition the indicator was attached with.
   void   Configure(ENUM_CRT_RANGE_MODE rangeMode, const int &sessionHours[], int atrPeriod,
                     bool useATRFilter, double minSweepPoints, double minSweepATRMult,
                     int maxReentryBars, double point, int minSweepStrength);
   // Lets the panel's live min-strength spinner (OnChangeStrength) keep the MTF A+ threshold
   // in sync without re-supplying the detection params Configure() also takes - see
   // CRT_ZonesPanel.mqh's OnChangeStrength, which already updates g_min_sweep_strength live.
   void   SetMinSweepStrength(int minSweepStrength) { m_minSweepStrength = (minSweepStrength >= 1) ? minSweepStrength : 2; }
   void   ScanAll(const string symbol, const int lookback_bars);

   // Same as ScanAll(), except the ONE tracked timeframe matching currentPeriod (if any) is not
   // re-scanned via CopyRates/a throwaway engine at all - its signal is decided directly from
   // liveEngine (the main indicator's own, continuously-updated g_engine), per design spec S4:
   // "la temporalidad del grafico actual no se re-escanea - se reusa el resultado que el
   // indicador ya calcula en OnCalculate". This is what OnTimer() calls; ScanAll() itself stays
   // available standalone (and spec-signature-exact) for the other 5 slots / direct testing.
   void   ScanAllReusingCurrent(const string symbol, const int lookback_bars,
                                  const ENUM_TIMEFRAMES currentPeriod, const CCRTZonesEngine &liveEngine);

   ENUM_ZI_MTF_SIGNAL Signal(const int tf_index) const;

   // Index (0..5) of `period` among the 6 tracked timeframes, or -1 if it isn't one of them.
   int    IndexForPeriod(const ENUM_TIMEFRAMES period) const;

   // Decides BUY/SELL/NONE from an already-populated engine's current zone list, WITHOUT
   // mutating it (mitigated zones are skipped, never physically removed via RemoveMitigated) -
   // this is what makes it safe to call directly against a shared/live engine such as the main
   // indicator's own g_engine (see ScanAllReusingCurrent): a destructive RemoveMitigated() call
   // from an OnTimer-driven scan could race SyncZoneObjects()'s own pending-deletion bookkeeping
   // in CRT_ZonesInd.mq5 and orphan chart objects. Exposed (not private) so the headless test
   // suite can drive it with synthetic engines, bypassing CopyRates - see CRT_Test_MTFSignals
   // and CRT_Test_MTFCurrentTimeframeReuse in CRT_TestSuite.mqh.
   ENUM_ZI_MTF_SIGNAL DecideSignal(const CCRTZonesEngine &eng) const;
};

//+------------------------------------------------------------------+
CCRTZonesMTFScanner::CCRTZonesMTFScanner(void)
{
   for(int i = 0; i < 6; i++) m_signal[i] = ZI_MTF_NONE;
   m_tfs[0] = PERIOD_M1;  m_tfs[1] = PERIOD_M5;  m_tfs[2] = PERIOD_M15;
   m_tfs[3] = PERIOD_H1;  m_tfs[4] = PERIOD_H4;  m_tfs[5] = PERIOD_D1;
   m_rangeMode        = CRT_RANGE_DAILY;
   m_sessionHours[0] = 0; m_sessionHours[1] = 8; m_sessionHours[2] = 13;
   m_atrPeriod        = 14;
   m_useATRFilter     = true;
   m_minSweepPoints   = 50.0;
   m_minSweepATRMult  = 0.25;
   m_maxReentryBars   = 10;
   m_point            = 0.0001;
   m_minSweepStrength = 2;
}

//+------------------------------------------------------------------+
void CCRTZonesMTFScanner::Configure(ENUM_CRT_RANGE_MODE rangeMode, const int &sessionHours[], int atrPeriod,
                                     bool useATRFilter, double minSweepPoints, double minSweepATRMult,
                                     int maxReentryBars, double point, int minSweepStrength)
{
   m_rangeMode       = rangeMode;
   for(int k = 0; k < 3; k++) m_sessionHours[k] = sessionHours[k];
   m_atrPeriod       = atrPeriod;
   m_useATRFilter    = useATRFilter;
   m_minSweepPoints  = minSweepPoints;
   m_minSweepATRMult = minSweepATRMult;
   m_maxReentryBars  = maxReentryBars;
   m_point           = point;
   m_minSweepStrength = (minSweepStrength >= 1) ? minSweepStrength : 2;
}

//+------------------------------------------------------------------+
void CCRTZonesMTFScanner::ScanAll(const string symbol, const int lookback_bars)
{
   for(int t = 0; t < 6; t++)
      m_signal[t] = ScanTimeframe(symbol, m_tfs[t], lookback_bars);
}

//+------------------------------------------------------------------+
void CCRTZonesMTFScanner::ScanAllReusingCurrent(const string symbol, const int lookback_bars,
                                                  const ENUM_TIMEFRAMES currentPeriod, const CCRTZonesEngine &liveEngine)
{
   for(int t = 0; t < 6; t++)
      m_signal[t] = (m_tfs[t] == currentPeriod) ? DecideSignal(liveEngine)
                                                 : ScanTimeframe(symbol, m_tfs[t], lookback_bars);
}

//+------------------------------------------------------------------+
int CCRTZonesMTFScanner::IndexForPeriod(const ENUM_TIMEFRAMES period) const
{
   for(int i = 0; i < 6; i++)
      if(m_tfs[i] == period) return i;
   return -1;
}

//+------------------------------------------------------------------+
ENUM_ZI_MTF_SIGNAL CCRTZonesMTFScanner::Signal(const int tf_index) const
{
   if(tf_index < 0 || tf_index >= 6) return ZI_MTF_NONE;
   return m_signal[tf_index];
}

//+------------------------------------------------------------------+
//| Copies bars for one timeframe (no indicator handle), feeds them   |
//| bar-by-bar into a fresh throwaway engine (same call shape as      |
//| CRT_ZonesInd.mq5's own OnCalculate history-replay loop, limit=0), |
//| then decides the signal from the resulting zone list. Nothing     |
//| here persists across calls - the engine and copied arrays are     |
//| local, so repeated timer-driven scans cannot leak or accumulate   |
//| state. Each call gets its OWN fresh CCRTZonesEngine instance (no  |
//| state shared with the main chart's g_engine or between the 5      |
//| non-current timeframes), configured from this scanner's own fixed |
//| m_rangeMode/m_sessionHours/... (see Configure()'s range-mode note |
//| on the class) - never the main chart's live ResetRangeMode()      |
//| override.                                                          |
//+------------------------------------------------------------------+
ENUM_ZI_MTF_SIGNAL CCRTZonesMTFScanner::ScanTimeframe(const string symbol, const ENUM_TIMEFRAMES tf, const int lookback_bars)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(symbol, tf, 0, lookback_bars, rates);
   if(copied < 10) return ZI_MTF_NONE; // guard: not enough data on this timeframe (or CopyRates failed)

   // Flip to oldest-first indexing to match ProcessClosedBar's own convention (same as the
   // time[]/open[]/... arrays OnCalculate passes: index 0 = oldest, last index = current bar).
   ArraySetAsSeries(rates, false);

   datetime time[]; double open[], high[], low[], close[];
   ArrayResize(time, copied);
   ArrayResize(open, copied);
   ArrayResize(high, copied);
   ArrayResize(low, copied);
   ArrayResize(close, copied);
   for(int k = 0; k < copied; k++)
   {
      time[k]  = rates[k].time;
      open[k]  = rates[k].open;
      high[k]  = rates[k].high;
      low[k]   = rates[k].low;
      close[k] = rates[k].close;
   }

   CCRTZonesEngine eng;
   eng.Configure(m_rangeMode, m_sessionHours, m_atrPeriod, m_useATRFilter,
                 m_minSweepPoints, m_minSweepATRMult, m_maxReentryBars, m_point);

   for(int i = 0; i < copied - 1; i++) // exclude the last (current/forming) bar, like OnCalculate does
      eng.ProcessClosedBar(i, time, open, high, low, close);

   return DecideSignal(eng);
}

//+------------------------------------------------------------------+
//| Signal rule - ADOPTED STANDARD for all 3 Zone Indicators (SMC/CRT/ |
//| VWAP MTF scanners must all implement this identical rule; design   |
//| spec S2/S6, cross-direction interpretation and tie-break ruled by  |
//| the controller on 2026-09-23 after Task 1 review):                 |
//|                                                                     |
//|  1. Per direction (BUY, SELL) independently: the most RECENT        |
//|     non-mitigated zone decides that direction's candidate, with an |
//|     A+ zone (strength >= min sweep strength) preferred over a      |
//|     normal one of the SAME direction when both coexist.            |
//|  2. If only one direction has an active candidate, it wins         |
//|     outright (NONE if neither does).                               |
//|  3. If BOTH directions have an active candidate: A+ BEATS NORMAL   |
//|     ACROSS directions too - this is the only place the A+-priority |
//|     rule is externally observable, since ENUM_ZI_MTF_SIGNAL has no |
//|     separate A+ value (only BUY/SELL/NONE).                        |
//|  4. If both (or neither) candidate is A+, the more RECENTLY formed |
//|     one wins; an exact tie (equal bar_time) favors BUY.            |
//+------------------------------------------------------------------+
ENUM_ZI_MTF_SIGNAL CCRTZonesMTFScanner::DecideSignal(const CCRTZonesEngine &eng) const
{
   int n = eng.ZonesTotal();

   bool     haveBuyAplus = false, haveBuyNormal = false, haveSellAplus = false, haveSellNormal = false;
   datetime bestBuyAplus = 0, bestBuyNormal = 0, bestSellAplus = 0, bestSellNormal = 0;

   for(int i = 0; i < n; i++)
   {
      if(eng.IsMitigated(i)) continue; // skip, don't remove - eng may be a shared/live engine (see class comment)
      ZI_Zone z;
      if(!eng.GetZone(i, z)) continue;
      bool aplus = (z.strength >= m_minSweepStrength);
      if(z.type == ZI_BUY)
      {
         if(aplus) { if(!haveBuyAplus || z.bar_time > bestBuyAplus) { haveBuyAplus = true; bestBuyAplus = z.bar_time; } }
         else      { if(!haveBuyNormal || z.bar_time > bestBuyNormal) { haveBuyNormal = true; bestBuyNormal = z.bar_time; } }
      }
      else
      {
         if(aplus) { if(!haveSellAplus || z.bar_time > bestSellAplus) { haveSellAplus = true; bestSellAplus = z.bar_time; } }
         else      { if(!haveSellNormal || z.bar_time > bestSellNormal) { haveSellNormal = true; bestSellNormal = z.bar_time; } }
      }
   }

   bool haveBuy  = haveBuyAplus  || haveBuyNormal;
   bool haveSell = haveSellAplus || haveSellNormal;

   if(!haveBuy && !haveSell) return ZI_MTF_NONE;
   if(haveBuy  && !haveSell) return ZI_MTF_BUY;
   if(haveSell && !haveBuy)  return ZI_MTF_SELL;

   if(haveBuyAplus && !haveSellAplus) return ZI_MTF_BUY;
   if(haveSellAplus && !haveBuyAplus) return ZI_MTF_SELL;

   datetime buyTime  = haveBuyAplus  ? bestBuyAplus  : bestBuyNormal;
   datetime sellTime = haveSellAplus ? bestSellAplus : bestSellNormal;
   return (sellTime > buyTime) ? ZI_MTF_SELL : ZI_MTF_BUY;
}

CCRTZonesMTFScanner g_mtf_scanner;

#endif // CRT_ZONES_MTF_MQH
