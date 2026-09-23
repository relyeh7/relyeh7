//+------------------------------------------------------------------+
//| CRT_ZonesEngine.mqh - pure detection logic for CRT_ZonesInd       |
//| Bidirectional Candle Range Theory zones: a reference range        |
//| (previous Daily/4H/Session period's high/low) is frozen, then the |
//| following period is scanned for a manipulation sweep beyond that  |
//| range and a distribution/reentry close back inside it.            |
//| No chart objects are drawn here - the main .mq5 owns OBJ_* calls. |
//|                                                                    |
//| Basado en mql5.com/es/articles/18911 (Christian Benjamin) -       |
//|   CRangePattern's true-range/ATR formula (large/small range vs.   |
//|   ATR multiple) is the basis for the strength filter below.       |
//|   ADAPTED, not instantiated: CRangePattern recomputes a fresh     |
//|   ATR window every call from *series*-ordered arrays (index 0 =   |
//|   newest). This engine follows Task 3's incremental, forward-only |
//|   convention (chronological arrays, one bar per call, persistent  |
//|   engine state) to stay consistent with the suite's OnCalculate   |
//|   wiring and to make ATR O(1) per bar instead of O(atrPeriod).    |
//|   The reference-range/sweep/reentry state machine itself has no   |
//|   corpus precedent (see ZoneIndicators\docs\mined-patterns.md     |
//|   section 2) - it is original logic built from the CRT            |
//|   methodology description in the design spec section 4.2.         |
//+------------------------------------------------------------------+
#ifndef CRT_ZONES_ENGINE_MQH
#define CRT_ZONES_ENGINE_MQH

#property strict

#include <ZoneIndicators\ZI_Common.mqh>

#define CRT_MAX_ZONES 200

enum ENUM_CRT_RANGE_MODE
{
   CRT_RANGE_DAILY   = 0,
   CRT_RANGE_H4      = 1,
   CRT_RANGE_SESSION = 2
};

//+------------------------------------------------------------------+
//| Returns the start-of-bucket time for the reference-range period   |
//| that bar time `t` belongs to. Daily = midnight-to-midnight; H4 =  |
//| four-hour blocks within the day; Session = the latest of the      |
//| three configured session-start hours (broker/server time, same    |
//| convention as time[]) at or before t's time-of-day, wrapping to   |
//| the previous day's last session if t falls before all of them.    |
//| sessionHours[] need not be sorted - the max-at-or-below search    |
//| does not depend on order.                                         |
//+------------------------------------------------------------------+
datetime CRT_BucketStart(const datetime t, const ENUM_CRT_RANGE_MODE mode, const int &sessionHours[])
{
   long tt  = (long)t;
   long day = tt - (tt % 86400);
   if(mode == CRT_RANGE_DAILY)
      return (datetime)day;

   long secOfDay = tt - day;
   if(mode == CRT_RANGE_H4)
   {
      long bucket = secOfDay - (secOfDay % 14400);
      return (datetime)(day + bucket);
   }

   // CRT_RANGE_SESSION
   long bestSec = -1;
   for(int k = 0; k < 3; k++)
   {
      long s = (long)sessionHours[k] * 3600;
      if(s <= secOfDay && s > bestSec)
         bestSec = s;
   }
   if(bestSec >= 0)
      return (datetime)(day + bestSec);

   // Before all sessions today: belongs to yesterday's latest session.
   long maxSec = 0;
   for(int k = 0; k < 3; k++)
   {
      long s = (long)sessionHours[k] * 3600;
      if(s > maxSec) maxSec = s;
   }
   return (datetime)(day - 86400 + maxSec);
}

//+------------------------------------------------------------------+
//| CCRTZonesEngine                                                   |
//+------------------------------------------------------------------+
class CCRTZonesEngine
{
private:
   ZI_Zone  m_zones[];
   bool     m_touched[];
   ZI_Zone  m_pendingDeletions[];

   ENUM_CRT_RANGE_MODE m_rangeMode;
   int      m_sessionHours[3];
   int      m_atrPeriod;
   bool     m_useATRFilter;
   double   m_minSweepPoints;
   double   m_minSweepATRMult;
   int      m_maxReentryBars;
   double   m_point;

   //--- reference-range / bucket state
   bool     m_bucketInit;
   datetime m_curBucket;
   double   m_buildHi, m_buildLo;     // current (still-open) period's running high/low
   bool     m_hasRange;
   double   m_rangeHi, m_rangeLo;     // frozen reference range (the just-completed period)

   //--- incremental ATR (true-range average), see file header note
   bool     m_atrInitialized;
   double   m_atrValue;
   double   m_atrSum;
   int      m_atrCount;
   bool     m_prevCloseSet;
   double   m_prevClose;

   //--- pending sweep-awaiting-reentry state, one slot per direction
   bool     m_pendingBuyActive;
   double   m_pendingBuyExtreme;
   datetime m_pendingBuyTime;
   int      m_pendingBuyBars;

   bool     m_pendingSellActive;
   double   m_pendingSellExtreme;
   datetime m_pendingSellTime;
   int      m_pendingSellBars;

   void     UpdateATR(const double h, const double l, const double c);
   void     AddZone(double hiIn, double loIn, ENUM_ZI_TYPE type, datetime t, int strength);
   void     ConfirmZone(ENUM_ZI_TYPE type, double zoneHi, double zoneLo, datetime t, double thresholdPrice);

public:
   void     Configure(ENUM_CRT_RANGE_MODE rangeMode, const int &sessionHours[], int atrPeriod,
                       bool useATRFilter, double minSweepPoints, double minSweepATRMult,
                       int maxReentryBars, double point);
   void     ResetRangeMode(ENUM_CRT_RANGE_MODE newMode);

   void     ProcessClosedBar(int i, const datetime &time[], const double &open[],
                              const double &high[], const double &low[], const double &close[]);
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

   ENUM_CRT_RANGE_MODE RangeMode(void) const { return m_rangeMode; }
   bool     HasRange(void) const { return m_hasRange; }
   double   RangeHi(void)  const { return m_rangeHi; }
   double   RangeLo(void)  const { return m_rangeLo; }
   bool     PendingBuyActive(void)  const { return m_pendingBuyActive; }
   bool     PendingSellActive(void) const { return m_pendingSellActive; }
};

//+------------------------------------------------------------------+
void CCRTZonesEngine::Configure(ENUM_CRT_RANGE_MODE rangeMode, const int &sessionHours[], int atrPeriod,
                                 bool useATRFilter, double minSweepPoints, double minSweepATRMult,
                                 int maxReentryBars, double point)
{
   m_rangeMode       = rangeMode;
   for(int k = 0; k < 3; k++) m_sessionHours[k] = sessionHours[k];
   m_atrPeriod       = (atrPeriod > 1) ? atrPeriod : 14;
   m_useATRFilter    = useATRFilter;
   m_minSweepPoints  = (minSweepPoints >= 0.0) ? minSweepPoints : 0.0;
   m_minSweepATRMult = (minSweepATRMult >= 0.0) ? minSweepATRMult : 0.0;
   m_maxReentryBars  = (maxReentryBars > 0) ? maxReentryBars : 10;
   m_point           = (point > 0.0) ? point : 0.0001;

   ArrayResize(m_zones, 0);
   ArrayResize(m_touched, 0);
   ArrayResize(m_pendingDeletions, 0);

   m_bucketInit = false;
   m_curBucket  = 0;
   m_buildHi = 0.0; m_buildLo = 0.0;
   m_hasRange = false;
   m_rangeHi = 0.0; m_rangeLo = 0.0;

   m_atrInitialized = false;
   m_atrValue = 0.0; m_atrSum = 0.0; m_atrCount = 0;
   m_prevCloseSet = false; m_prevClose = 0.0;

   m_pendingBuyActive = false; m_pendingBuyExtreme = 0.0; m_pendingBuyTime = 0; m_pendingBuyBars = 0;
   m_pendingSellActive = false; m_pendingSellExtreme = 0.0; m_pendingSellTime = 0; m_pendingSellBars = 0;
}

//+------------------------------------------------------------------+
//| Switches the reference-range grouping mode without discarding     |
//| zones already confirmed - only the live bucket/range/pending      |
//| state resets, so detection resumes cleanly under the new mode     |
//| from the next processed bar. Called by the panel's mode selector. |
//+------------------------------------------------------------------+
void CCRTZonesEngine::ResetRangeMode(ENUM_CRT_RANGE_MODE newMode)
{
   m_rangeMode  = newMode;
   m_bucketInit = false;
   m_curBucket  = 0;
   m_hasRange   = false;
   m_pendingBuyActive  = false;
   m_pendingSellActive = false;
}

//+------------------------------------------------------------------+
//| Wilder-style rolling true-range average - same formula as         |
//| CRangePattern's ATR (see file header), computed incrementally     |
//| instead of by rescanning a window every call.                     |
//+------------------------------------------------------------------+
void CCRTZonesEngine::UpdateATR(const double h, const double l, const double c)
{
   double tr;
   if(m_prevCloseSet)
      tr = MathMax(h - l, MathMax(MathAbs(h - m_prevClose), MathAbs(l - m_prevClose)));
   else
      tr = h - l;

   if(!m_atrInitialized)
   {
      m_atrSum += tr;
      m_atrCount++;
      if(m_atrCount >= m_atrPeriod)
      {
         m_atrValue = m_atrSum / m_atrPeriod;
         m_atrInitialized = true;
      }
   }
   else
   {
      m_atrValue = (m_atrValue * (m_atrPeriod - 1) + tr) / m_atrPeriod;
   }

   m_prevClose = c;
   m_prevCloseSet = true;
}

//+------------------------------------------------------------------+
void CCRTZonesEngine::AddZone(double hiIn, double loIn, ENUM_ZI_TYPE type, datetime t, int strength)
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
   m_zones[n].label     = "CRT";
   m_touched[n] = false;

   if(n + 1 > CRT_MAX_ZONES)
   {
      // Same eviction contract as SMC_ZonesEngine: queue the dropped zone so the
      // caller can delete its chart objects too, instead of orphaning them.
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
//| Strength: 1 base, +1 if the sweep cleared the threshold distance  |
//| by 2x, +1 more at 3x - rewards a deeper (more decisive) sweep.    |
//| With no active filter (thresholdPrice==0) strength stays at 1.    |
//+------------------------------------------------------------------+
void CCRTZonesEngine::ConfirmZone(ENUM_ZI_TYPE type, double zoneHi, double zoneLo, datetime t, double thresholdPrice)
{
   double depth = MathAbs(zoneHi - zoneLo);
   int strength = 1;
   if(thresholdPrice > 0.0)
   {
      if(depth >= 3.0 * thresholdPrice)      strength = 3;
      else if(depth >= 2.0 * thresholdPrice) strength = 2;
   }
   AddZone(zoneHi, zoneLo, type, t, strength);
}

//+------------------------------------------------------------------+
void CCRTZonesEngine::ProcessClosedBar(int i, const datetime &time[], const double &open[],
                                        const double &high[], const double &low[], const double &close[])
{
   datetime bucket = CRT_BucketStart(time[i], m_rangeMode, m_sessionHours);

   if(!m_bucketInit)
   {
      m_bucketInit = true;
      m_curBucket  = bucket;
      m_buildHi = high[i];
      m_buildLo = low[i];
      UpdateATR(high[i], low[i], close[i]);
      return; // no reference range yet - nothing to sweep against
   }

   if(bucket != m_curBucket)
   {
      // Period rolled over: the period just completed becomes the frozen
      // reference range; a new period starts building from this bar.
      m_rangeHi = m_buildHi;
      m_rangeLo = m_buildLo;
      m_hasRange = true;
      m_curBucket = bucket;
      m_buildHi = high[i];
      m_buildLo = low[i];
      // A new reference range invalidates any sweep still awaiting reentry
      // against the old one.
      m_pendingBuyActive  = false;
      m_pendingSellActive = false;
   }
   else
   {
      if(high[i] > m_buildHi) m_buildHi = high[i];
      if(low[i]  < m_buildLo) m_buildLo = low[i];
   }

   UpdateATR(high[i], low[i], close[i]);

   if(!m_hasRange)
      return;
   if(m_useATRFilter && !m_atrInitialized)
      return; // ATR warm-up: skip sweep detection rather than filter with a false zero

   double thresholdPrice = m_useATRFilter ? (m_minSweepATRMult * m_atrValue) : (m_minSweepPoints * m_point);
   if(thresholdPrice < 0.0) thresholdPrice = 0.0;

   //--- BUY side: manipulation sweep below the reference range low, then a
   //--- distribution/reentry close back above it (same bar or a later one).
   if(m_pendingBuyActive)
   {
      if(low[i] < m_pendingBuyExtreme) m_pendingBuyExtreme = low[i];
      if(close[i] > m_rangeLo)
      {
         ConfirmZone(ZI_BUY, m_rangeLo, m_pendingBuyExtreme, time[i], thresholdPrice);
         m_pendingBuyActive = false;
      }
      else
      {
         m_pendingBuyBars++;
         if(m_pendingBuyBars > m_maxReentryBars)
            m_pendingBuyActive = false; // expired: manipulation without distribution, no zone
      }
   }
   else if(low[i] < m_rangeLo - thresholdPrice)
   {
      if(close[i] > m_rangeLo)
         ConfirmZone(ZI_BUY, m_rangeLo, low[i], time[i], thresholdPrice); // same-bar reentry
      else
      {
         m_pendingBuyActive  = true;
         m_pendingBuyExtreme = low[i];
         m_pendingBuyTime    = time[i];
         m_pendingBuyBars    = 0;
      }
   }

   //--- SELL side: mirror, sweep above the reference range high.
   if(m_pendingSellActive)
   {
      if(high[i] > m_pendingSellExtreme) m_pendingSellExtreme = high[i];
      if(close[i] < m_rangeHi)
      {
         ConfirmZone(ZI_SELL, m_pendingSellExtreme, m_rangeHi, time[i], thresholdPrice);
         m_pendingSellActive = false;
      }
      else
      {
         m_pendingSellBars++;
         if(m_pendingSellBars > m_maxReentryBars)
            m_pendingSellActive = false;
      }
   }
   else if(high[i] > m_rangeHi + thresholdPrice)
   {
      if(close[i] < m_rangeHi)
         ConfirmZone(ZI_SELL, high[i], m_rangeHi, time[i], thresholdPrice);
      else
      {
         m_pendingSellActive  = true;
         m_pendingSellExtreme = high[i];
         m_pendingSellTime    = time[i];
         m_pendingSellBars    = 0;
      }
   }

   CheckMitigation(close[i]);
}

//+------------------------------------------------------------------+
//| A zone is invalidated once price closes all the way through it    |
//| without reversing: past price_hi for a sell zone, past price_lo   |
//| for a buy zone. Same rule as SMC_ZonesEngine.                     |
//+------------------------------------------------------------------+
void CCRTZonesEngine::CheckMitigation(double lastClose)
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
void CCRTZonesEngine::RemoveMitigated(void)
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
bool CCRTZonesEngine::GetZone(int idx, ZI_Zone &out) const
{
   if(idx < 0 || idx >= ArraySize(m_zones)) return false;
   out = m_zones[idx];
   return true;
}

bool CCRTZonesEngine::GetPendingDeletion(int idx, ZI_Zone &out) const
{
   if(idx < 0 || idx >= ArraySize(m_pendingDeletions)) return false;
   out = m_pendingDeletions[idx];
   return true;
}

bool CCRTZonesEngine::IsMitigated(int idx) const
{
   if(idx < 0 || idx >= ArraySize(m_zones)) return true;
   return m_zones[idx].mitigated;
}

bool CCRTZonesEngine::WasTouched(int idx) const
{
   if(idx < 0 || idx >= ArraySize(m_touched)) return false;
   return m_touched[idx];
}

void CCRTZonesEngine::MarkTouched(int idx)
{
   if(idx < 0 || idx >= ArraySize(m_touched)) return;
   m_touched[idx] = true;
}

#endif // CRT_ZONES_ENGINE_MQH
