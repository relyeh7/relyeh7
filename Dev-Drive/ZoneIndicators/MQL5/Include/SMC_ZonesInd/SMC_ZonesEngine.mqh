//+------------------------------------------------------------------+
//| SMC_ZonesEngine.mqh - pure detection logic for SMC_ZonesInd      |
//| Bidirectional Smart-Money-Concepts zones: Order Blocks, Fair     |
//| Value Gaps, equal-high/low liquidity sweeps, premium/discount.   |
//| No chart objects are drawn here - the main .mq5 owns OBJ_* calls.|
//|                                                                    |
//| Basado en mql5.com/es/articles/15899 (Niquel Mendoza) - deteccion|
//|   de Order Blocks (impulso >=Nx cuerpo de la vela previa)         |
//| Basado en mql5.com/es/articles/18669 (Eugene Mmene) - deteccion   |
//|   de Fair Value Gap de 3 velas, bidireccional                     |
//| Basado en mql5.com/es/articles/18379 (lynnchris) - liquidity      |
//|   sweep de un maximo/minimo previo (bull/bear); el agrupamiento   |
//|   de maximos/minimos iguales en un "pool" de liquidez es logica   |
//|   original, sin precedente compilado en el corpus (ver            |
//|   ZoneIndicators\docs\mined-patterns.md seccion 1c).               |
//+------------------------------------------------------------------+
#ifndef SMC_ZONES_ENGINE_MQH
#define SMC_ZONES_ENGINE_MQH

#property strict

#include <ZoneIndicators\ZI_Common.mqh>

#define SMC_MAX_ZONES   200
#define SMC_MAX_SWINGS  100

struct SMC_SwingPoint
{
   double   price;
   datetime time;
};

//+------------------------------------------------------------------+
//| CSMCZonesEngine                                                   |
//+------------------------------------------------------------------+
class CSMCZonesEngine
{
private:
   ZI_Zone         m_zones[];
   bool            m_touched[];      // parallel array, same index space as m_zones
   ZI_Zone         m_pendingDeletions[]; // zones evicted by the SMC_MAX_ZONES cap, awaiting
                                          // chart-object cleanup by the caller (see PendingDeletion*)
   SMC_SwingPoint  m_swingHighs[];
   SMC_SwingPoint  m_swingLows[];

   double          m_impulseFactor;      // OB: impulse body >= factor * ob-candle body
   double          m_fvgMinPoints;       // FVG: minimum gap size, in points
   double          m_eqTolerancePoints;  // EQH/EQL: clustering tolerance, in points
   int             m_rangeLookbackBars;  // premium/discount range window
   int             m_swingLookbackBars;  // how many bars a swing stays eligible for the pool
   double          m_point;

   double          m_rangeHi;
   double          m_rangeLo;
   bool            m_isPremium;

   void   UpdateRange(const double &high[], const double &low[], int i);
   void   AddSwingHigh(double price, datetime t);
   void   AddSwingLow(double price, datetime t);
   void   PruneSwingsOlderThan(datetime cutoff);
   bool   FindSweptHighPool(double barHigh, double tol, double &poolLevel);
   bool   FindSweptLowPool(double barLow, double tol, double &poolLevel);
   void   AddZone(double hiIn, double loIn, ENUM_ZI_TYPE type, datetime t,
                  const string labelTag, bool isPremium);
   void   UpdateConfluence(int newIndex, bool isPremium);

public:
   void   Configure(double impulseFactor, double fvgMinPoints, double eqTolerancePoints,
                     int rangeLookbackBars, int swingLookbackBars, double point);
   void   ProcessClosedBar(int i, const datetime &time[], const double &open[],
                            const double &high[], const double &low[], const double &close[]);
   void   CheckMitigation(double lastClose);
   void   RemoveMitigated(void);

   int    ZonesTotal(void) const { return ArraySize(m_zones); }
   bool   GetZone(int idx, ZI_Zone &out) const;
   bool   IsMitigated(int idx) const;
   bool   WasTouched(int idx) const;
   void   MarkTouched(int idx);

   // Zones the SMC_MAX_ZONES cap evicted from m_zones (oldest-first) since the last drain.
   // The engine draws nothing itself, so it cannot delete their chart objects - the caller
   // must drain this every time it reconciles chart objects (see SMC_ZonesInd.mq5's
   // SyncZoneObjects), or an evicted zone's OBJ_RECTANGLE/OBJ_TEXT is orphaned forever.
   int    PendingDeletionsTotal(void) const { return ArraySize(m_pendingDeletions); }
   bool   GetPendingDeletion(int idx, ZI_Zone &out) const;
   void   ClearPendingDeletions(void) { ArrayResize(m_pendingDeletions, 0); }

   bool   IsPremium(void) const { return m_isPremium; }
   double RangeHi(void)   const { return m_rangeHi; }
   double RangeLo(void)   const { return m_rangeLo; }
   double RangeMid(void)  const { return (m_rangeHi + m_rangeLo) / 2.0; }
};

//+------------------------------------------------------------------+
void CSMCZonesEngine::Configure(double impulseFactor, double fvgMinPoints, double eqTolerancePoints,
                                 int rangeLookbackBars, int swingLookbackBars, double point)
{
   m_impulseFactor     = (impulseFactor > 0.0) ? impulseFactor : 3.0;
   m_fvgMinPoints      = (fvgMinPoints >= 0.0) ? fvgMinPoints : 0.0;
   m_eqTolerancePoints = (eqTolerancePoints > 0.0) ? eqTolerancePoints : 5.0;
   m_rangeLookbackBars = (rangeLookbackBars > 1) ? rangeLookbackBars : 50;
   m_swingLookbackBars = (swingLookbackBars > 1) ? swingLookbackBars : 50;
   m_point             = (point > 0.0) ? point : 0.0001;
   m_rangeHi = 0.0;
   m_rangeLo = 0.0;
   m_isPremium = false;
   ArrayResize(m_zones, 0);
   ArrayResize(m_touched, 0);
   ArrayResize(m_pendingDeletions, 0);
   ArrayResize(m_swingHighs, 0);
   ArrayResize(m_swingLows, 0);
}

//+------------------------------------------------------------------+
void CSMCZonesEngine::UpdateRange(const double &high[], const double &low[], int i)
{
   int from = i - m_rangeLookbackBars + 1;
   if(from < 0) from = 0;
   double hi = high[i];
   double lo = low[i];
   for(int k = from; k <= i; k++)
   {
      if(high[k] > hi) hi = high[k];
      if(low[k]  < lo) lo = low[k];
   }
   m_rangeHi = hi;
   m_rangeLo = lo;
}

//+------------------------------------------------------------------+
void CSMCZonesEngine::AddSwingHigh(double price, datetime t)
{
   int n = ArraySize(m_swingHighs);
   ArrayResize(m_swingHighs, n + 1);
   m_swingHighs[n].price = price;
   m_swingHighs[n].time  = t;
   if(n + 1 > SMC_MAX_SWINGS)
   {
      for(int k = 0; k < n; k++) m_swingHighs[k] = m_swingHighs[k + 1];
      ArrayResize(m_swingHighs, n);
   }
}

void CSMCZonesEngine::AddSwingLow(double price, datetime t)
{
   int n = ArraySize(m_swingLows);
   ArrayResize(m_swingLows, n + 1);
   m_swingLows[n].price = price;
   m_swingLows[n].time  = t;
   if(n + 1 > SMC_MAX_SWINGS)
   {
      for(int k = 0; k < n; k++) m_swingLows[k] = m_swingLows[k + 1];
      ArrayResize(m_swingLows, n);
   }
}

//+------------------------------------------------------------------+
void CSMCZonesEngine::PruneSwingsOlderThan(datetime cutoff)
{
   int n = ArraySize(m_swingHighs);
   int kept = 0;
   for(int k = 0; k < n; k++)
      if(m_swingHighs[k].time >= cutoff)
      {
         if(kept != k) m_swingHighs[kept] = m_swingHighs[k];
         kept++;
      }
   if(kept != n) ArrayResize(m_swingHighs, kept);

   n = ArraySize(m_swingLows);
   kept = 0;
   for(int k = 0; k < n; k++)
      if(m_swingLows[k].time >= cutoff)
      {
         if(kept != k) m_swingLows[kept] = m_swingLows[k];
         kept++;
      }
   if(kept != n) ArrayResize(m_swingLows, kept);
}

//+------------------------------------------------------------------+
//| Groups swing points within `tol` of each other into a liquidity   |
//| pool (>=2 points = "equal highs/lows"); reports the pool whose    |
//| level the current bar's high/low has just swept (broken then, by |
//| the caller's own close check, rejected).                          |
//+------------------------------------------------------------------+
bool CSMCZonesEngine::FindSweptHighPool(double barHigh, double tol, double &poolLevel)
{
   int n = ArraySize(m_swingHighs);
   for(int i = 0; i < n; i++)
   {
      int matches = 1;
      double sum = m_swingHighs[i].price;
      for(int j = i + 1; j < n; j++)
         if(MathAbs(m_swingHighs[j].price - m_swingHighs[i].price) <= tol)
         {
            matches++;
            sum += m_swingHighs[j].price;
         }
      if(matches >= 2)
      {
         double level = sum / matches;
         if(barHigh > level)
         {
            poolLevel = level;
            return true;
         }
      }
   }
   return false;
}

bool CSMCZonesEngine::FindSweptLowPool(double barLow, double tol, double &poolLevel)
{
   int n = ArraySize(m_swingLows);
   for(int i = 0; i < n; i++)
   {
      int matches = 1;
      double sum = m_swingLows[i].price;
      for(int j = i + 1; j < n; j++)
         if(MathAbs(m_swingLows[j].price - m_swingLows[i].price) <= tol)
         {
            matches++;
            sum += m_swingLows[j].price;
         }
      if(matches >= 2)
      {
         double level = sum / matches;
         if(barLow < level)
         {
            poolLevel = level;
            return true;
         }
      }
   }
   return false;
}

//+------------------------------------------------------------------+
void CSMCZonesEngine::AddZone(double hiIn, double loIn, ENUM_ZI_TYPE type, datetime t,
                               const string labelTag, bool isPremium)
{
   double hi = MathMax(hiIn, loIn);
   double lo = MathMin(hiIn, loIn);

   int n = ArraySize(m_zones);
   ArrayResize(m_zones, n + 1);
   ArrayResize(m_touched, n + 1);
   m_zones[n].price_hi  = hi;
   m_zones[n].price_lo  = lo;
   m_zones[n].type      = type;
   m_zones[n].strength  = 1;
   m_zones[n].bar_time  = t;
   m_zones[n].mitigated = false;
   m_zones[n].label     = labelTag;
   m_touched[n] = false;

   UpdateConfluence(n, isPremium);

   if(n + 1 > SMC_MAX_ZONES)
   {
      // The oldest zone (index 0) is about to be dropped from m_zones, whether or not it
      // was ever mitigated - queue it so the caller can delete its chart objects too,
      // instead of orphaning them (it may already have an OBJ_RECTANGLE/OBJ_TEXT drawn).
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
//| Confluence rule: a new zone starts at strength 1; every other     |
//| active (non-mitigated) zone of the SAME direction whose price     |
//| range overlaps it adds +1 to both zones (stacking). A sell zone   |
//| formed while price sits in the premium half of the range, or a    |
//| buy zone formed in the discount half, gets a further +1.          |
//+------------------------------------------------------------------+
void CSMCZonesEngine::UpdateConfluence(int newIndex, bool isPremium)
{
   ENUM_ZI_TYPE t = m_zones[newIndex].type;
   double hi = m_zones[newIndex].price_hi;
   double lo = m_zones[newIndex].price_lo;

   for(int i = 0; i < newIndex; i++)
   {
      if(m_zones[i].mitigated) continue;
      if(m_zones[i].type != t) continue;
      bool overlap = (m_zones[i].price_lo <= hi && m_zones[i].price_hi >= lo);
      if(overlap)
      {
         m_zones[i].strength++;
         m_zones[newIndex].strength++;
      }
   }

   if(t == ZI_SELL && isPremium)  m_zones[newIndex].strength++;
   if(t == ZI_BUY  && !isPremium) m_zones[newIndex].strength++;
}

//+------------------------------------------------------------------+
void CSMCZonesEngine::ProcessClosedBar(int i, const datetime &time[], const double &open[],
                                        const double &high[], const double &low[], const double &close[])
{
   if(i < 3) return;

   UpdateRange(high, low, i);
   bool isPremium = (close[i] > RangeMid());
   m_isPremium = isPremium;

   //--- Order Block: impulse = bar i, OB candle = bar i-1
   double bodyImpulse = MathAbs(close[i] - open[i]);
   double bodyOB       = MathAbs(close[i - 1] - open[i - 1]);
   if(bodyOB < m_point) bodyOB = m_point;
   if(bodyImpulse >= m_impulseFactor * bodyOB)
   {
      if(close[i] < open[i])
         AddZone(high[i - 1], low[i - 1], ZI_SELL, time[i - 1], "OB", isPremium);
      else if(close[i] > open[i])
         AddZone(high[i - 1], low[i - 1], ZI_BUY, time[i - 1], "OB", isPremium);
   }

   //--- Fair Value Gap: candle1 = i-2 (oldest), candle2 = i-1, candle3 = i (newest)
   double minGap = m_fvgMinPoints * m_point;
   if(low[i] - high[i - 2] >= minGap)
      AddZone(low[i], high[i - 2], ZI_BUY, time[i - 1], "FVG", isPremium);
   if(low[i - 2] - high[i] >= minGap)
      AddZone(low[i - 2], high[i], ZI_SELL, time[i - 1], "FVG", isPremium);

   //--- Swing confirmation at i-1 (needs the just-closed bar i to confirm it)
   if(high[i - 1] > high[i - 2] && high[i - 1] > high[i])
      AddSwingHigh(high[i - 1], time[i - 1]);
   if(low[i - 1] < low[i - 2] && low[i - 1] < low[i])
      AddSwingLow(low[i - 1], time[i - 1]);

   long barSeconds = (i >= 1) ? (long)(time[i] - time[i - 1]) : 60;
   if(barSeconds <= 0) barSeconds = 60;
   PruneSwingsOlderThan(time[i] - (long)m_swingLookbackBars * barSeconds);

   //--- Liquidity sweep: bar i's wick sweeps a clustered equal-high/low pool, closes back inside
   double tol = m_eqTolerancePoints * m_point;
   double poolLevel;
   if(FindSweptHighPool(high[i], tol, poolLevel) && close[i] < poolLevel)
      AddZone(high[i], poolLevel, ZI_SELL, time[i], "SWEEP", isPremium);
   if(FindSweptLowPool(low[i], tol, poolLevel) && close[i] > poolLevel)
      AddZone(poolLevel, low[i], ZI_BUY, time[i], "SWEEP", isPremium);

   CheckMitigation(close[i]);
}

//+------------------------------------------------------------------+
//| A zone is invalidated once price closes all the way through it    |
//| without reversing: past price_hi for a sell zone, past price_lo   |
//| for a buy zone.                                                   |
//+------------------------------------------------------------------+
void CSMCZonesEngine::CheckMitigation(double lastClose)
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
void CSMCZonesEngine::RemoveMitigated(void)
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
bool CSMCZonesEngine::GetZone(int idx, ZI_Zone &out) const
{
   if(idx < 0 || idx >= ArraySize(m_zones)) return false;
   out = m_zones[idx];
   return true;
}

bool CSMCZonesEngine::GetPendingDeletion(int idx, ZI_Zone &out) const
{
   if(idx < 0 || idx >= ArraySize(m_pendingDeletions)) return false;
   out = m_pendingDeletions[idx];
   return true;
}

bool CSMCZonesEngine::IsMitigated(int idx) const
{
   if(idx < 0 || idx >= ArraySize(m_zones)) return true;
   return m_zones[idx].mitigated;
}

bool CSMCZonesEngine::WasTouched(int idx) const
{
   if(idx < 0 || idx >= ArraySize(m_touched)) return false;
   return m_touched[idx];
}

void CSMCZonesEngine::MarkTouched(int idx)
{
   if(idx < 0 || idx >= ArraySize(m_touched)) return;
   m_touched[idx] = true;
}

#endif // SMC_ZONES_ENGINE_MQH
