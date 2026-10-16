//+------------------------------------------------------------------+
//| VWAP_ZonesMTF.mqh - multi-timeframe buy/sell signal scanner for   |
//| VWAP_ZonesInd's panel row. Reuses CVWAPZonesEngine as-is (no new  |
//| detection logic) by feeding it CopyRates() bars from 6 fixed      |
//| timeframes through a fresh, throwaway engine instance per scan -  |
//| the same no-handle approach VWAP_ZonesInd already uses for its     |
//| own math. Pattern copied from ZoneIndicators\MQL5\Include\        |
//| CRT_ZonesInd\CRT_ZonesMTF.mqh (Task 2, approved with zero fix      |
//| rounds), cross-checked against SMC_ZonesMTF.mqh (Task 1).          |
//|                                                                    |
//| D1 SESSION-DEGENERATE CASE (task-3 design question, resolved       |
//| 2026-09-23 - chosen resolution: option (a), accept + document):    |
//| CVWAPZonesEngine resets its VWAP accumulators on a DAILY session   |
//| boundary (VWAP_DayBucket = floor(bar_time, 86400)). A D1 bar's own |
//| time[] value IS already that day's midnight bucket start, so on    |
//| the D1 timeframe every single bar starts a brand-new "session" -   |
//| the daily reset fires on literally every ProcessClosedBar() call.  |
//| Consequence, worked through the engine's own arithmetic: with      |
//| cumV/cumPV/cumPV2 restarted at zero for each D1 bar, VWAP for that  |
//| bar collapses to exactly ITS OWN typical price ((h+l+c)/3), and the |
//| variance identity (cumPV2/cumV - VWAP^2) reduces to typical^2 -     |
//| typical^2 = 0 - i.e. m_stdDev is EXACTLY 0.0 on every D1 bar, so    |
//| Band1Upper == Band1Lower == Band2Upper == Band2Lower == VWAP. The   |
//| "band touch" condition (low<=touchLower or high>=touchUpper)        |
//| degenerates into "low<=typical or high>=typical", which is true on |
//| almost every real bar (typical price sits between low and high by  |
//| construction) - so the touch filter stops being selective on D1.   |
//| The declining-volume-window and new-N-bar-extreme filters are NOT  |
//| affected (the exhaustion window is explicitly never cleared on a   |
//| session rollover - see VWAP_ZonesEngine.mqh's ProcessClosedBar     |
//| comment - it accumulates normally across D1 bars just like any     |
//| other timeframe), so a D1 zone can still fail to form on those two |
//| grounds; it just can never be rejected on the touch condition.     |
//| This is accepted here as a known, inherent limitation of a         |
//| session-VWAP indicator queried on its own daily chart (the D1 slot |
//| in the MTF row reflects this degenerate single-bar "VWAP", not a   |
//| meaningful multi-bar volume-weighted average) rather than silently |
//| special-cased with a coarser (e.g. weekly) reset boundary: doing   |
//| that would make the D1 MTF slot's notion of "VWAP" diverge from    |
//| what VWAP_ZonesInd itself would compute and draw if the user       |
//| actually switched their chart to D1 - which would be a worse,      |
//| harder-to-explain inconsistency than the documented degeneracy.    |
//| See VWAP_Test_MTFDailyDegenerateBands in Tests\VWAP_TestSuite.mqh   |
//| for the regression test that pins this exact behavior down.        |
//+------------------------------------------------------------------+
#ifndef VWAP_ZONES_MTF_MQH
#define VWAP_ZONES_MTF_MQH

#property strict

#include <ZoneIndicators\ZI_Common.mqh>
#include <VWAP_ZonesInd\VWAP_ZonesEngine.mqh>

enum ENUM_ZI_MTF_SIGNAL { ZI_MTF_NONE, ZI_MTF_BUY, ZI_MTF_SELL };

//+------------------------------------------------------------------+
//| Pure timing gate mirroring OnTimer()'s once-per-N-seconds         |
//| throttle. Free function (not a class member) so a headless test  |
//| can exercise it without TimeCurrent()/GetTickCount().             |
//+------------------------------------------------------------------+
bool VWAP_MTFShouldScan(const datetime lastScanTime, const datetime now, const int intervalSeconds)
{
   if(intervalSeconds <= 0) return true;
   return (now - lastScanTime) >= intervalSeconds;
}

//+------------------------------------------------------------------+
//| CVWAPZonesMTFScanner                                              |
//+------------------------------------------------------------------+
class CVWAPZonesMTFScanner
{
private:
   ENUM_ZI_MTF_SIGNAL m_signal[6];
   ENUM_TIMEFRAMES    m_tfs[6]; // single source of truth for the 6 tracked timeframes' order/identity,
                                 // shared by ScanAll(), ScanAllReusingCurrent() and IndexForPeriod()

   //--- Detection params, fixed for the scanner's lifetime (captured ONCE from the
   //--- indicator's static Inp* inputs at OnInit) and used identically by all 6
   //--- timeframe scans, including the D1 session-degenerate case documented above -
   //--- same rationale as CRT's Configure() note: each of the 6 scans applies the
   //--- SAME fixed detection-param definition the indicator was attached with.
   double   m_band1Mult;
   double   m_band2Mult;
   int      m_touchBand;
   int      m_exhaustionBars;
   bool     m_useRealVolume;
   double   m_point;
   int      m_minZoneStrength;

   ENUM_ZI_MTF_SIGNAL ScanTimeframe(const string symbol, const ENUM_TIMEFRAMES tf, const int lookback_bars);

public:
                     CVWAPZonesMTFScanner(void);

   void   Configure(double band1Mult, double band2Mult, int touchBand, int exhaustionBars,
                     bool useRealVolume, double point, int minZoneStrength);
   // Lets the panel's live min-strength spinner (OnChangeMinStrength) keep the MTF A+
   // threshold in sync without re-supplying the detection params Configure() also takes -
   // see VWAP_ZonesPanel.mqh's OnChangeMinStrength, which already updates g_min_zone_strength live.
   void   SetMinZoneStrength(int minZoneStrength) { m_minZoneStrength = (minZoneStrength >= 1) ? minZoneStrength : 2; }
   void   ScanAll(const string symbol, const int lookback_bars);

   // Same as ScanAll(), except the ONE tracked timeframe matching currentPeriod (if any) is not
   // re-scanned via CopyRates/a throwaway engine at all - its signal is decided directly from
   // liveEngine (the main indicator's own, continuously-updated g_engine), per design spec S4:
   // "la temporalidad del grafico actual no se re-escanea - se reusa el resultado que el
   // indicador ya calcula en OnCalculate". This is what OnTimer() calls; ScanAll() itself stays
   // available standalone (and spec-signature-exact) for the other 5 slots / direct testing.
   void   ScanAllReusingCurrent(const string symbol, const int lookback_bars,
                                  const ENUM_TIMEFRAMES currentPeriod, const CVWAPZonesEngine &liveEngine);

   ENUM_ZI_MTF_SIGNAL Signal(const int tf_index) const;

   // Index (0..5) of `period` among the 6 tracked timeframes, or -1 if it isn't one of them.
   int    IndexForPeriod(const ENUM_TIMEFRAMES period) const;

   // Decides BUY/SELL/NONE from an already-populated engine's current zone list, WITHOUT
   // mutating it (mitigated zones are skipped, never physically removed via RemoveMitigated) -
   // this is what makes it safe to call directly against a shared/live engine such as the main
   // indicator's own g_engine (see ScanAllReusingCurrent): a destructive RemoveMitigated() call
   // from an OnTimer-driven scan could race SyncZoneObjects()'s own pending-deletion bookkeeping
   // in VWAP_ZonesInd.mq5 and orphan chart objects. Exposed (not private) so the headless test
   // suite can drive it with synthetic engines, bypassing CopyRates - see VWAP_Test_MTFSignals
   // and VWAP_Test_MTFCurrentTimeframeReuse in VWAP_TestSuite.mqh.
   ENUM_ZI_MTF_SIGNAL DecideSignal(const CVWAPZonesEngine &eng) const;
};

//+------------------------------------------------------------------+
CVWAPZonesMTFScanner::CVWAPZonesMTFScanner(void)
{
   for(int i = 0; i < 6; i++) m_signal[i] = ZI_MTF_NONE;
   m_tfs[0] = PERIOD_M1;  m_tfs[1] = PERIOD_M5;  m_tfs[2] = PERIOD_M15;
   m_tfs[3] = PERIOD_H1;  m_tfs[4] = PERIOD_H4;  m_tfs[5] = PERIOD_D1;
   m_band1Mult       = 1.0;
   m_band2Mult       = 2.0;
   m_touchBand       = 1;
   m_exhaustionBars  = 5;
   m_useRealVolume   = false;
   m_point           = 0.0001;
   m_minZoneStrength = 2;
}

//+------------------------------------------------------------------+
void CVWAPZonesMTFScanner::Configure(double band1Mult, double band2Mult, int touchBand, int exhaustionBars,
                                      bool useRealVolume, double point, int minZoneStrength)
{
   m_band1Mult       = band1Mult;
   m_band2Mult       = band2Mult;
   m_touchBand       = (touchBand == 2) ? 2 : 1;
   m_exhaustionBars  = (exhaustionBars >= 2) ? exhaustionBars : 5;
   m_useRealVolume   = useRealVolume;
   m_point           = point;
   m_minZoneStrength = (minZoneStrength >= 1) ? minZoneStrength : 2;
}

//+------------------------------------------------------------------+
void CVWAPZonesMTFScanner::ScanAll(const string symbol, const int lookback_bars)
{
   for(int t = 0; t < 6; t++)
      m_signal[t] = ScanTimeframe(symbol, m_tfs[t], lookback_bars);
}

//+------------------------------------------------------------------+
void CVWAPZonesMTFScanner::ScanAllReusingCurrent(const string symbol, const int lookback_bars,
                                                   const ENUM_TIMEFRAMES currentPeriod, const CVWAPZonesEngine &liveEngine)
{
   for(int t = 0; t < 6; t++)
      m_signal[t] = (m_tfs[t] == currentPeriod) ? DecideSignal(liveEngine)
                                                 : ScanTimeframe(symbol, m_tfs[t], lookback_bars);
}

//+------------------------------------------------------------------+
int CVWAPZonesMTFScanner::IndexForPeriod(const ENUM_TIMEFRAMES period) const
{
   for(int i = 0; i < 6; i++)
      if(m_tfs[i] == period) return i;
   return -1;
}

//+------------------------------------------------------------------+
ENUM_ZI_MTF_SIGNAL CVWAPZonesMTFScanner::Signal(const int tf_index) const
{
   if(tf_index < 0 || tf_index >= 6) return ZI_MTF_NONE;
   return m_signal[tf_index];
}

//+------------------------------------------------------------------+
//| Copies bars for one timeframe (no indicator handle), feeds them   |
//| bar-by-bar into a fresh throwaway engine (same call shape as      |
//| VWAP_ZonesInd.mq5's own OnCalculate history-replay loop, limit=0),|
//| then decides the signal from the resulting zone list. Nothing     |
//| here persists across calls - the engine and copied arrays are     |
//| local, so repeated timer-driven scans cannot leak or accumulate   |
//| state. Each call gets its OWN fresh CVWAPZonesEngine instance (no |
//| state shared with the main chart's g_engine or between the 5      |
//| non-current timeframes), configured from this scanner's own fixed |
//| m_band1Mult/m_band2Mult/... (see Configure()'s doc comment on the |
//| class). tick_volume/real_volume come straight off the MqlRates    |
//| struct CopyRates() already fills in - no separate CopyTickVolume/ |
//| CopyRealVolume call needed. See the file header for the D1        |
//| session-degenerate case this loop runs into on that one timeframe.|
//+------------------------------------------------------------------+
ENUM_ZI_MTF_SIGNAL CVWAPZonesMTFScanner::ScanTimeframe(const string symbol, const ENUM_TIMEFRAMES tf, const int lookback_bars)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(symbol, tf, 0, lookback_bars, rates);
   if(copied < 10) return ZI_MTF_NONE; // guard: not enough data on this timeframe (or CopyRates failed)

   // Flip to oldest-first indexing to match ProcessClosedBar's own convention (same as the
   // time[]/high[]/... arrays OnCalculate passes: index 0 = oldest, last index = current bar).
   ArraySetAsSeries(rates, false);

   datetime time[]; double high[], low[], close[]; long tickVolume[], realVolume[];
   ArrayResize(time, copied);
   ArrayResize(high, copied);
   ArrayResize(low, copied);
   ArrayResize(close, copied);
   ArrayResize(tickVolume, copied);
   ArrayResize(realVolume, copied);
   for(int k = 0; k < copied; k++)
   {
      time[k]       = rates[k].time;
      high[k]       = rates[k].high;
      low[k]        = rates[k].low;
      close[k]      = rates[k].close;
      tickVolume[k] = rates[k].tick_volume;
      realVolume[k] = rates[k].real_volume;
   }

   CVWAPZonesEngine eng;
   eng.Configure(m_band1Mult, m_band2Mult, m_touchBand, m_exhaustionBars, m_useRealVolume, m_point);

   for(int i = 0; i < copied - 1; i++) // exclude the last (current/forming) bar, like OnCalculate does
      eng.ProcessClosedBar(i, time, high, low, close, tickVolume, realVolume);

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
//|     A+ zone (strength >= min zone strength) preferred over a       |
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
ENUM_ZI_MTF_SIGNAL CVWAPZonesMTFScanner::DecideSignal(const CVWAPZonesEngine &eng) const
{
   int n = eng.ZonesTotal();

   bool     haveBuyAplus = false, haveBuyNormal = false, haveSellAplus = false, haveSellNormal = false;
   datetime bestBuyAplus = 0, bestBuyNormal = 0, bestSellAplus = 0, bestSellNormal = 0;

   for(int i = 0; i < n; i++)
   {
      if(eng.IsMitigated(i)) continue; // skip, don't remove - eng may be a shared/live engine (see class comment)
      ZI_Zone z;
      if(!eng.GetZone(i, z)) continue;
      bool aplus = (z.strength >= m_minZoneStrength);
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

CVWAPZonesMTFScanner g_mtf_scanner;

#endif // VWAP_ZONES_MTF_MQH
