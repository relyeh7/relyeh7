//+------------------------------------------------------------------+
//| VWAP_ZonesEngine.mqh - pure detection logic for VWAP_ZonesInd     |
//| Session VWAP (daily reset) + volume-weighted deviation bands      |
//| (+-1sigma/+-2sigma) with bidirectional volume-exhaustion zone     |
//| detection at band touches. No chart objects/plots are drawn here |
//| - the main .mq5 owns OBJ_* calls and indicator buffer writes.     |
//|                                                                    |
//| Basado en mql5.com/es/articles/10329 (Daniel Jose) - session VWAP |
//|   core (reset on session/day change, running Sum(v*typical)/     |
//|   Sum(v)). ADAPTED, not copied: the article's snippet uses        |
//|   volume[] (broker real volume) and a static-local rescan-to-     |
//|   session-start loop driven by re-detecting the boundary from a   |
//|   full array each call. This engine follows the suite's           |
//|   incremental, forward-only convention (CRT_ZonesEngine's         |
//|   UpdateATR is the model): persistent engine-object state,        |
//|   ProcessClosedBar() called once per closed bar, cumulative sums   |
//|   reset in O(1) the moment the day changes - no rescan needed.     |
//|   Uses tick_volume[] by default per design spec Section 4.3's      |
//|   VOLUME_TICK/VOLUME_REAL fallback note (see EffectiveVolume()).   |
//|                                                                    |
//| Basado en mql5.com/es/articles/130 (Sergey Greecie) - the          |
//|   center +/- k*StdDev band-construction TECHNIQUE only (its        |
//|   iStdDev-handle-around-a-plain-MA implementation is NOT used;     |
//|   mined-patterns.md section 3b explicitly warns that isn't         |
//|   volume-weighted or centered on VWAP). Per mined-patterns.md's    |
//|   "exact" recommendation (accumulate Sum(volume*(typical-VWAP)^2) |
//|   in the session loop), this engine computes the true volume-      |
//|   weighted variance around VWAP. Taken completely literally that   |
//|   recommendation is NOT O(1) per bar, because VWAP is itself a     |
//|   moving target that changes every bar - summing squared           |
//|   deviations against a moving target would need either an          |
//|   O(bars) rescan or the algebraic expansion used here:             |
//|     Sum(v*(tp-VWAP)^2) = Sum(v*tp^2) - 2*VWAP*Sum(v*tp) + VWAP^2*Sum(v) |
//|   and since VWAP = Sum(v*tp)/Sum(v), this reduces to the standard  |
//|   volume-weighted "E[X^2]-E[X]^2" identity:                        |
//|     variance = cumPV2/cumV - VWAP^2                                |
//|   (cumPV2 = running Sum(v*typical^2), accumulated alongside cumPV  |
//|   and cumV every bar). This keeps the O(1)-per-bar incremental-    |
//|   state convention the whole suite uses while still computing the  |
//|   exact volume-weighted stddev the recommendation calls for, not   |
//|   the iStdDev-around-a-plain-MA approximation it warns against.    |
//|   Documented per this suite's convention for judgment calls (see   |
//|   Task 4's ATR-adaptation note in CRT_ZonesEngine.mqh).            |
//|                                                                    |
//| Volume-exhaustion detection (declining volume over N bars while    |
//| price makes a new N-bar extreme near a VWAP band) has NO corpus    |
//| precedent - mined-patterns.md section 3c is explicit that no       |
//| article in the corpus implements a rule-based volume-exhaustion    |
//| detector (the two closest hits both depend on an ONNX/LSTM model,  |
//| disproportionate for this indicator). This is original logic       |
//| built directly from that section's recommended arithmetic over     |
//| tick_volume[]/volume[], not adapted from any compiled precedent.   |
//+------------------------------------------------------------------+
#ifndef VWAP_ZONES_ENGINE_MQH
#define VWAP_ZONES_ENGINE_MQH

#property strict

#include <ZoneIndicators\ZI_Common.mqh>

#define VWAP_MAX_ZONES 200

//+------------------------------------------------------------------+
//| Start-of-day bucket for a bar time - daily session reset only     |
//| (design spec Section 4.3 specifies "VWAP de sesion, reset diario",|
//| no configurable session-hours anchor like CRT's range modes).     |
//| Broker/server time, same convention as CRT_BucketStart - no GMT   |
//| offset correction attempted.                                      |
//+------------------------------------------------------------------+
datetime VWAP_DayBucket(const datetime t)
{
   long tt = (long)t;
   return (datetime)(tt - (tt % 86400));
}

//+------------------------------------------------------------------+
//| CVWAPZonesEngine                                                  |
//+------------------------------------------------------------------+
class CVWAPZonesEngine
{
private:
   ZI_Zone  m_zones[];
   bool     m_touched[];
   ZI_Zone  m_pendingDeletions[];

   double   m_band1Mult;
   double   m_band2Mult;
   int      m_touchBand;        // 1 or 2 - which sigma band counts as a "touch" for zone emission
   int      m_exhaustionBars;   // N: total bars (incl. touch bar) required in the declining-volume chain
   bool     m_useRealVolume;
   double   m_point;

   //--- session VWAP state (daily reset)
   bool     m_sessionInit;
   datetime m_curDay;
   double   m_cumPV;            // running Sum(volume * typical_price)
   double   m_cumPV2;           // running Sum(volume * typical_price^2) - see file header derivation
   double   m_cumV;             // running Sum(volume)
   double   m_vwap;
   double   m_stdDev;
   bool     m_vwapReady;        // true once cumV > 0 for the current session

   //--- last computed band levels (as of the last processed bar)
   double   m_band1Upper, m_band1Lower;
   double   m_band2Upper, m_band2Lower;

   //--- exhaustion window: the (exhaustionBars-1) bars immediately BEFORE the
   //--- bar currently being evaluated. Evaluated first, pushed after - see
   //--- ProcessClosedBar().
   double   m_volWindow[];
   double   m_lowWindow[];
   double   m_highWindow[];
   int      m_windowCapacity;   // = m_exhaustionBars - 1
   int      m_windowCount;      // bars currently held, caps at m_windowCapacity

   double   EffectiveVolume(const int i, const long &tickVolume[], const long &realVolume[]) const;
   void     PushWindow(double vol, double lo, double hi);
   bool     WindowFull(void) const { return m_windowCount >= m_windowCapacity; }
   double   MinOfLowWindow(void) const;
   double   MaxOfHighWindow(void) const;
   bool     IsDecliningIncludingCurrent(double currentVol) const;

   void     AddZone(double hiIn, double loIn, ENUM_ZI_TYPE type, datetime t, int strength);

public:
   void     Configure(double band1Mult, double band2Mult, int touchBand, int exhaustionBars,
                       bool useRealVolume, double point);
   void     SetTouchBand(int touchBand) { m_touchBand = (touchBand == 2) ? 2 : 1; }
   void     SetExhaustionBars(int exhaustionBars);

   void     ProcessClosedBar(int i, const datetime &time[], const double &high[], const double &low[],
                              const double &close[], const long &tickVolume[], const long &realVolume[]);
   void     CheckMitigation(double lastClose);
   void     RemoveMitigated(void);

   int      ZonesTotal(void) const { return ArraySize(m_zones); }
   bool     GetZone(int idx, ZI_Zone &out) const;
   bool     IsMitigated(int idx) const;
   bool     WasTouched(int idx) const;
   void     MarkTouched(int idx);

   int      PendingDeletionsTotal(void) const { return ArraySize(m_pendingDeletions); }
   bool     GetPendingDeletion(int idx, ZI_Zone &out) const;
   void     ClearPendingDeletions(void) { ArrayResize(m_pendingDeletions, 0); }

   int      TouchBand(void)      const { return m_touchBand; }
   int      ExhaustionBars(void) const { return m_exhaustionBars; }
   bool     VWAPReady(void)  const { return m_vwapReady; }
   double   VWAP(void)       const { return m_vwap; }
   double   Band1Upper(void) const { return m_band1Upper; }
   double   Band1Lower(void) const { return m_band1Lower; }
   double   Band2Upper(void) const { return m_band2Upper; }
   double   Band2Lower(void) const { return m_band2Lower; }
};

//+------------------------------------------------------------------+
void CVWAPZonesEngine::Configure(double band1Mult, double band2Mult, int touchBand, int exhaustionBars,
                                  bool useRealVolume, double point)
{
   m_band1Mult = (band1Mult > 0.0) ? band1Mult : 1.0;
   m_band2Mult = (band2Mult > 0.0) ? band2Mult : 2.0;
   m_touchBand = (touchBand == 2) ? 2 : 1;
   m_useRealVolume = useRealVolume;
   m_point = (point > 0.0) ? point : 0.0001;

   ArrayResize(m_zones, 0);
   ArrayResize(m_touched, 0);
   ArrayResize(m_pendingDeletions, 0);

   m_sessionInit = false;
   m_curDay = 0;
   m_cumPV = 0.0; m_cumPV2 = 0.0; m_cumV = 0.0;
   m_vwap = 0.0; m_stdDev = 0.0; m_vwapReady = false;
   m_band1Upper = 0.0; m_band1Lower = 0.0;
   m_band2Upper = 0.0; m_band2Lower = 0.0;

   m_exhaustionBars = 0; // forces SetExhaustionBars to (re)allocate the window arrays below
   SetExhaustionBars((exhaustionBars >= 2) ? exhaustionBars : 5);
}

//+------------------------------------------------------------------+
//| Live-safe: resizes/restarts the exhaustion window without          |
//| touching the VWAP session accumulators or any confirmed zones -   |
//| same "reconfigure live params, keep zone history" contract as     |
//| CRT_ZonesEngine::ResetRangeMode().                                  |
//+------------------------------------------------------------------+
void CVWAPZonesEngine::SetExhaustionBars(int exhaustionBars)
{
   m_exhaustionBars = (exhaustionBars >= 2) ? exhaustionBars : 2;
   m_windowCapacity = m_exhaustionBars - 1;
   ArrayResize(m_volWindow, m_windowCapacity);
   ArrayResize(m_lowWindow, m_windowCapacity);
   ArrayResize(m_highWindow, m_windowCapacity);
   m_windowCount = 0;
}

//+------------------------------------------------------------------+
//| VOLUME_TICK vs VOLUME_REAL fallback (design spec Section 4.3): not|
//| every symbol/broker provides reliable real volume, so real volume |
//| is only used, per bar, when InpUseRealVolume is enabled AND that   |
//| specific bar's real volume is > 0. A bar reporting 0 real volume   |
//| (broker doesn't supply it for that bar) silently falls back to    |
//| tick volume instead of corrupting the session's cumulative sums    |
//| with zeros.                                                        |
//+------------------------------------------------------------------+
double CVWAPZonesEngine::EffectiveVolume(const int i, const long &tickVolume[], const long &realVolume[]) const
{
   if(m_useRealVolume && realVolume[i] > 0)
      return (double)realVolume[i];
   return (double)tickVolume[i];
}

//+------------------------------------------------------------------+
void CVWAPZonesEngine::PushWindow(double vol, double lo, double hi)
{
   if(m_windowCapacity <= 0) return;
   if(m_windowCount < m_windowCapacity)
   {
      m_volWindow[m_windowCount]  = vol;
      m_lowWindow[m_windowCount]  = lo;
      m_highWindow[m_windowCount] = hi;
      m_windowCount++;
   }
   else
   {
      for(int k = 0; k < m_windowCapacity - 1; k++)
      {
         m_volWindow[k]  = m_volWindow[k + 1];
         m_lowWindow[k]  = m_lowWindow[k + 1];
         m_highWindow[k] = m_highWindow[k + 1];
      }
      m_volWindow[m_windowCapacity - 1]  = vol;
      m_lowWindow[m_windowCapacity - 1]  = lo;
      m_highWindow[m_windowCapacity - 1] = hi;
   }
}

double CVWAPZonesEngine::MinOfLowWindow(void) const
{
   double m = m_lowWindow[0];
   for(int k = 1; k < m_windowCount; k++)
      if(m_lowWindow[k] < m) m = m_lowWindow[k];
   return m;
}

double CVWAPZonesEngine::MaxOfHighWindow(void) const
{
   double m = m_highWindow[0];
   for(int k = 1; k < m_windowCount; k++)
      if(m_highWindow[k] > m) m = m_highWindow[k];
   return m;
}

//+------------------------------------------------------------------+
//| "Volumen decreciente durante N barras": the window (the            |
//| exhaustionBars-1 bars immediately before the current one) plus the |
//| current bar's own volume must form one unbroken non-increasing     |
//| chain, oldest to newest - exactly N values in the chain.           |
//+------------------------------------------------------------------+
bool CVWAPZonesEngine::IsDecliningIncludingCurrent(double currentVol) const
{
   if(!WindowFull()) return false;
   for(int k = 1; k < m_windowCount; k++)
      if(m_volWindow[k] > m_volWindow[k - 1]) return false;
   if(m_windowCount > 0 && currentVol > m_volWindow[m_windowCount - 1]) return false;
   return true;
}

//+------------------------------------------------------------------+
void CVWAPZonesEngine::AddZone(double hiIn, double loIn, ENUM_ZI_TYPE type, datetime t, int strength)
{
   double hi = MathMax(hiIn, loIn);
   double lo = MathMin(hiIn, loIn);

   int n = ArraySize(m_zones);
   ArrayResize(m_zones, n + 1);
   ArrayResize(m_touched, n + 1);
   m_zones[n].price_hi  = hi;
   m_zones[n].price_lo  = lo;
   m_zones[n].type      = type;
   m_zones[n].strength  = strength;
   m_zones[n].bar_time  = t;
   m_zones[n].mitigated = false;
   m_zones[n].label     = "VWAP";
   m_touched[n] = false;

   if(n + 1 > VWAP_MAX_ZONES)
   {
      // Same eviction contract as SMC/CRT_ZonesEngine: queue the dropped zone
      // so the caller can delete its chart objects too, instead of orphaning them.
      int pd = ArraySize(m_pendingDeletions);
      ArrayResize(m_pendingDeletions, pd + 1);
      m_pendingDeletions[pd] = m_zones[0];

      for(int k = 0; k < n; k++)
      {
         m_zones[k]   = m_zones[k + 1];
         m_touched[k] = m_touched[k + 1];
      }
      ArrayResize(m_zones, n);
      ArrayResize(m_touched, n);
   }
}

//+------------------------------------------------------------------+
//| Processes one closed bar: updates the session VWAP/bands, then     |
//| evaluates volume-exhaustion zone conditions against the window as  |
//| it stood BEFORE this bar (so "new N-bar extreme" and "N-bar        |
//| declining volume" both genuinely include this bar as the chain's   |
//| newest/most-extreme element), and only then pushes this bar into   |
//| the window for the next call.                                      |
//+------------------------------------------------------------------+
void CVWAPZonesEngine::ProcessClosedBar(int i, const datetime &time[], const double &high[], const double &low[],
                                         const double &close[], const long &tickVolume[], const long &realVolume[])
{
   datetime day = VWAP_DayBucket(time[i]);
   if(!m_sessionInit || day != m_curDay)
   {
      m_sessionInit = true;
      m_curDay = day;
      m_cumPV = 0.0; m_cumPV2 = 0.0; m_cumV = 0.0;
      m_vwapReady = false;
      // NOTE: the exhaustion window is intentionally NOT cleared on a session
      // rollover - volume-exhaustion is a short-term (N-bar) pattern that can
      // legitimately straddle a session boundary; only the VWAP anchor itself
      // resets daily per design spec Section 4.3.
   }

   double typical = (high[i] + low[i] + close[i]) / 3.0;
   double vol = EffectiveVolume(i, tickVolume, realVolume);
   if(vol < 0.0) vol = 0.0;

   m_cumPV  += typical * vol;
   m_cumPV2 += typical * typical * vol;
   m_cumV   += vol;

   if(m_cumV > 0.0)
   {
      m_vwap = m_cumPV / m_cumV;
      double variance = m_cumPV2 / m_cumV - m_vwap * m_vwap;
      if(variance < 0.0) variance = 0.0; // guards float rounding in the E[X^2]-E[X]^2 identity
      m_stdDev = MathSqrt(variance);
      m_vwapReady = true;
   }
   else
   {
      m_vwap = 0.0; m_stdDev = 0.0; m_vwapReady = false;
   }

   m_band1Upper = m_vwap + m_band1Mult * m_stdDev;
   m_band1Lower = m_vwap - m_band1Mult * m_stdDev;
   m_band2Upper = m_vwap + m_band2Mult * m_stdDev;
   m_band2Lower = m_vwap - m_band2Mult * m_stdDev;

   if(m_vwapReady)
   {
      double touchLowerLevel = (m_touchBand == 2) ? m_band2Lower : m_band1Lower;
      double touchUpperLevel = (m_touchBand == 2) ? m_band2Upper : m_band1Upper;

      bool touchedLower = (low[i]  <= touchLowerLevel);
      bool touchedUpper = (high[i] >= touchUpperLevel);
      bool declining     = IsDecliningIncludingCurrent(vol);
      bool newLow        = WindowFull() && (low[i]  < MinOfLowWindow());
      bool newHigh       = WindowFull() && (high[i] > MaxOfHighWindow());

      if(touchedLower && declining && newLow)
      {
         int strength = 1;
         if(low[i] <= m_band2Lower) strength++; // deeper than the 2-sigma band too, extra confluence
         if(m_windowCount > 0 && m_volWindow[0] > 0.0 && vol <= m_volWindow[0] * 0.5) strength++; // sharp decline across the whole window
         AddZone(low[i], touchLowerLevel, ZI_BUY, time[i], strength);
      }
      if(touchedUpper && declining && newHigh)
      {
         int strength = 1;
         if(high[i] >= m_band2Upper) strength++;
         if(m_windowCount > 0 && m_volWindow[0] > 0.0 && vol <= m_volWindow[0] * 0.5) strength++;
         AddZone(touchUpperLevel, high[i], ZI_SELL, time[i], strength);
      }
   }

   PushWindow(vol, low[i], high[i]);
   CheckMitigation(close[i]);
}

//+------------------------------------------------------------------+
//| A zone is invalidated once price closes all the way through it    |
//| without reversing - same rule as SMC/CRT_ZonesEngine.              |
//+------------------------------------------------------------------+
void CVWAPZonesEngine::CheckMitigation(double lastClose)
{
   int n = ArraySize(m_zones);
   for(int i = 0; i < n; i++)
   {
      if(m_zones[i].mitigated) continue;
      if(m_zones[i].type == ZI_SELL && lastClose > m_zones[i].price_hi) m_zones[i].mitigated = true;
      if(m_zones[i].type == ZI_BUY  && lastClose < m_zones[i].price_lo) m_zones[i].mitigated = true;
   }
}

//+------------------------------------------------------------------+
void CVWAPZonesEngine::RemoveMitigated(void)
{
   int n = ArraySize(m_zones);
   int kept = 0;
   for(int i = 0; i < n; i++)
      if(!m_zones[i].mitigated)
      {
         if(kept != i)
         {
            m_zones[kept]   = m_zones[i];
            m_touched[kept] = m_touched[i];
         }
         kept++;
      }
   if(kept != n)
   {
      ArrayResize(m_zones, kept);
      ArrayResize(m_touched, kept);
   }
}

//+------------------------------------------------------------------+
bool CVWAPZonesEngine::GetZone(int idx, ZI_Zone &out) const
{
   if(idx < 0 || idx >= ArraySize(m_zones)) return false;
   out = m_zones[idx];
   return true;
}

bool CVWAPZonesEngine::GetPendingDeletion(int idx, ZI_Zone &out) const
{
   if(idx < 0 || idx >= ArraySize(m_pendingDeletions)) return false;
   out = m_pendingDeletions[idx];
   return true;
}

bool CVWAPZonesEngine::IsMitigated(int idx) const
{
   if(idx < 0 || idx >= ArraySize(m_zones)) return true;
   return m_zones[idx].mitigated;
}

bool CVWAPZonesEngine::WasTouched(int idx) const
{
   if(idx < 0 || idx >= ArraySize(m_touched)) return false;
   return m_touched[idx];
}

void CVWAPZonesEngine::MarkTouched(int idx)
{
   if(idx < 0 || idx >= ArraySize(m_touched)) return;
   m_touched[idx] = true;
}

#endif // VWAP_ZONES_ENGINE_MQH
