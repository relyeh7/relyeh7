//+------------------------------------------------------------------+
//| SMC_ZonesMTF.mqh - multi-timeframe buy/sell signal scanner for    |
//| SMC_ZonesInd's panel row. Reuses CSMCZonesEngine as-is (no new    |
//| detection logic) by feeding it CopyRates() bars from 6 fixed      |
//| timeframes through a fresh, throwaway engine instance per scan -  |
//| the same no-handle approach VWAP_ZonesInd uses for its own math.  |
//+------------------------------------------------------------------+
#ifndef SMC_ZONES_MTF_MQH
#define SMC_ZONES_MTF_MQH

#property strict

#include <ZoneIndicators\ZI_Common.mqh>
#include <SMC_ZonesInd\SMC_ZonesEngine.mqh>

enum ENUM_ZI_MTF_SIGNAL { ZI_MTF_NONE, ZI_MTF_BUY, ZI_MTF_SELL };

//+------------------------------------------------------------------+
//| Pure timing gate mirroring OnTimer()'s once-per-N-seconds         |
//| throttle. Free function (not a class member) so a headless test  |
//| can exercise it without TimeCurrent()/GetTickCount().             |
//+------------------------------------------------------------------+
bool SMC_MTFShouldScan(const datetime lastScanTime, const datetime now, const int intervalSeconds)
{
   if(intervalSeconds <= 0) return true;
   return (now - lastScanTime) >= intervalSeconds;
}

//+------------------------------------------------------------------+
//| CSMCZonesMTFScanner                                               |
//+------------------------------------------------------------------+
class CSMCZonesMTFScanner
{
private:
   ENUM_ZI_MTF_SIGNAL m_signal[6];

   double   m_impulseFactor;
   double   m_fvgMinPoints;
   double   m_eqTolerancePoints;
   int      m_rangeLookbackBars;
   int      m_swingLookbackBars;
   double   m_point;
   int      m_minConfluence;

   ENUM_ZI_MTF_SIGNAL ScanTimeframe(const string symbol, const ENUM_TIMEFRAMES tf, const int lookback_bars);

public:
                     CSMCZonesMTFScanner(void);

   void   Configure(double impulseFactor, double fvgMinPoints, double eqTolerancePoints,
                     int rangeLookbackBars, int swingLookbackBars, double point, int minConfluence);
   // Lets the panel's live confluence spinner (OnChangeConfluence) keep the MTF A+ threshold
   // in sync without re-supplying the detection params Configure() also takes - see
   // SMC_ZonesPanel.mqh's OnChangeConfluence, which already updates g_min_confluence live.
   void   SetMinConfluence(int minConfluence) { m_minConfluence = (minConfluence >= 1) ? minConfluence : 2; }
   void   ScanAll(const string symbol, const int lookback_bars);
   ENUM_ZI_MTF_SIGNAL Signal(const int tf_index) const;

   // Decides BBUY/SELL/NONE from an already-populated engine's current zone list. Exposed
   // (not private) so the headless test suite can drive it with synthetic engines, bypassing
   // CopyRates - see SMC_Test_MTFSignals in SMC_TestSuite.mqh.
   ENUM_ZI_MTF_SIGNAL DecideSignal(CSMCZonesEngine &eng);
};

//+------------------------------------------------------------------+
CSMCZonesMTFScanner::CSMCZonesMTFScanner(void)
{
   for(int i = 0; i < 6; i++) m_signal[i] = ZI_MTF_NONE;
   m_impulseFactor      = 3.0;
   m_fvgMinPoints       = 0.0;
   m_eqTolerancePoints  = 5.0;
   m_rangeLookbackBars  = 50;
   m_swingLookbackBars  = 50;
   m_point              = 0.0001;
   m_minConfluence      = 2;
}

//+------------------------------------------------------------------+
void CSMCZonesMTFScanner::Configure(double impulseFactor, double fvgMinPoints, double eqTolerancePoints,
                                     int rangeLookbackBars, int swingLookbackBars, double point, int minConfluence)
{
   m_impulseFactor     = impulseFactor;
   m_fvgMinPoints      = fvgMinPoints;
   m_eqTolerancePoints = eqTolerancePoints;
   m_rangeLookbackBars = rangeLookbackBars;
   m_swingLookbackBars = swingLookbackBars;
   m_point             = point;
   m_minConfluence     = (minConfluence >= 1) ? minConfluence : 2;
}

//+------------------------------------------------------------------+
void CSMCZonesMTFScanner::ScanAll(const string symbol, const int lookback_bars)
{
   ENUM_TIMEFRAMES tfs[6] = { PERIOD_M1, PERIOD_M5, PERIOD_M15, PERIOD_H1, PERIOD_H4, PERIOD_D1 };
   for(int t = 0; t < 6; t++)
      m_signal[t] = ScanTimeframe(symbol, tfs[t], lookback_bars);
}

//+------------------------------------------------------------------+
ENUM_ZI_MTF_SIGNAL CSMCZonesMTFScanner::Signal(const int tf_index) const
{
   if(tf_index < 0 || tf_index >= 6) return ZI_MTF_NONE;
   return m_signal[tf_index];
}

//+------------------------------------------------------------------+
//| Copies bars for one timeframe (no indicator handle), feeds them   |
//| bar-by-bar into a fresh throwaway engine (same call shape as      |
//| SMC_ZonesInd.mq5's own OnCalculate history-replay loop), then      |
//| decides the signal from the resulting zone list. Nothing here     |
//| persists across calls - the engine and copied arrays are local,   |
//| so repeated timer-driven scans cannot leak or accumulate state.   |
//+------------------------------------------------------------------+
ENUM_ZI_MTF_SIGNAL CSMCZonesMTFScanner::ScanTimeframe(const string symbol, const ENUM_TIMEFRAMES tf, const int lookback_bars)
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

   CSMCZonesEngine eng;
   eng.Configure(m_impulseFactor, m_fvgMinPoints, m_eqTolerancePoints,
                 m_rangeLookbackBars, m_swingLookbackBars, m_point);

   int limit = 3;
   for(int i = limit; i < copied - 1; i++) // exclude the last (current/forming) bar, like OnCalculate does
      eng.ProcessClosedBar(i, time, open, high, low, close);

   return DecideSignal(eng);
}

//+------------------------------------------------------------------+
//| Signal rule (design spec S2/S6): for each direction, the most     |
//| recent non-mitigated zone decides that direction's candidate,     |
//| with an A+ zone (strength >= min confluence) preferred over a     |
//| normal one of the SAME direction. If only one direction has an    |
//| active candidate, it wins outright. If both directions have one,  |
//| A+ beats normal ACROSS directions too (this is the only place the |
//| rule is observable, since ENUM_ZI_MTF_SIGNAL has no separate A+    |
//| value); if both (or neither) candidate is A+, the more recently   |
//| formed one wins, ties favoring BUY.                                |
//+------------------------------------------------------------------+
ENUM_ZI_MTF_SIGNAL CSMCZonesMTFScanner::DecideSignal(CSMCZonesEngine &eng)
{
   eng.RemoveMitigated();
   int n = eng.ZonesTotal();

   bool     haveBuyAplus = false, haveBuyNormal = false, haveSellAplus = false, haveSellNormal = false;
   datetime bestBuyAplus = 0, bestBuyNormal = 0, bestSellAplus = 0, bestSellNormal = 0;

   for(int i = 0; i < n; i++)
   {
      ZI_Zone z;
      if(!eng.GetZone(i, z)) continue;
      bool aplus = (z.strength >= m_minConfluence);
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

CSMCZonesMTFScanner g_mtf_scanner;

#endif // SMC_ZONES_MTF_MQH
