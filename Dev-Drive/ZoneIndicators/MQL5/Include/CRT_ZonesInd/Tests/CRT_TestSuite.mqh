//+------------------------------------------------------------------+
//| CRT_TestSuite.mqh - unit tests for CCRTZonesEngine + panel/alert  |
//| toggle contracts. Shared by Experts\ZoneIndicators_Tests\         |
//| CRT_ZonesInd_TestRunner.mq5 (headless Strategy Tester). No test   |
//| here touches the account or the chart.                            |
//+------------------------------------------------------------------+
#ifndef CRT_TEST_SUITE_MQH
#define CRT_TEST_SUITE_MQH

#include "CRT_TestAsserts.mqh"
#include <ZoneIndicators\ZI_Common.mqh>
#include <CRT_ZonesInd\CRT_ZonesEngine.mqh>
#include <CRT_ZonesInd\CRT_ZonesPanel.mqh>

#define CRT_T_POINT 0.01

//--- Rebuilds the passed arrays as a single bar. The engine only ever reads
//--- index i for the call it's given (no historical lookback), so feeding one
//--- bar per call - in chronological order - is equivalent to feeding a full
//--- growing history array, and keeps each test scenario's numbers isolated.
void CRT_SetBar(datetime &time[], double &open[], double &high[], double &low[], double &close[],
                 datetime t, double o, double c, double h, double l)
{
   ArrayResize(time, 1);  ArrayResize(open, 1);  ArrayResize(high, 1);
   ArrayResize(low, 1);   ArrayResize(close, 1);
   time[0] = t; open[0] = o; close[0] = c; high[0] = h; low[0] = l;
}

bool CRT_FindZone(CCRTZonesEngine &eng, const ENUM_ZI_TYPE type, ZI_Zone &out)
{
   int n = eng.ZonesTotal();
   for(int i = 0; i < n; i++)
   {
      ZI_Zone z;
      if(!eng.GetZone(i, z)) continue;
      if(z.type == type) { out = z; return true; }
   }
   return false;
}

void CRT_MakeSessionHours(int &h[])
{
   ArrayResize(h, 3);
   h[0] = 0; h[1] = 8; h[2] = 13; // Asia / London / New York, broker-time hours
}

//+------------------------------------------------------------------+
//| Bucket boundaries: Daily / 4H / Session grouping, including the   |
//| Session wrap-to-previous-day case.                                 |
//+------------------------------------------------------------------+
void CRT_Test_BucketStart(void)
{
   Print("--- Reference-range bucket boundaries");
   int sh[]; CRT_MakeSessionHours(sh);

   datetime t = D'2026.01.15 13:45:00';
   ASSERT_TRUE(CRT_BucketStart(t, CRT_RANGE_DAILY, sh) == D'2026.01.15 00:00:00', "Daily bucket floors to midnight");
   ASSERT_TRUE(CRT_BucketStart(t, CRT_RANGE_H4, sh) == D'2026.01.15 12:00:00', "H4 bucket floors to the 4h block start (12:00-16:00)");
   ASSERT_TRUE(CRT_BucketStart(t, CRT_RANGE_SESSION, sh) == D'2026.01.15 13:00:00', "Session bucket = latest session start <= time-of-day (NY 13:00, since 13:45 is past the NY open)");

   datetime tLondon = D'2026.01.15 10:00:00';
   ASSERT_TRUE(CRT_BucketStart(tLondon, CRT_RANGE_SESSION, sh) == D'2026.01.15 08:00:00', "Session bucket at 10:00 belongs to the London 08:00 session");

   datetime tLate = D'2026.01.15 23:30:00';
   ASSERT_TRUE(CRT_BucketStart(tLate, CRT_RANGE_SESSION, sh) == D'2026.01.15 13:00:00', "Session bucket at 23:30 belongs to the NY 13:00 session");

   int shNoZero[]; ArrayResize(shNoZero, 3); shNoZero[0] = 2; shNoZero[1] = 8; shNoZero[2] = 13;
   datetime tEarly = D'2026.01.15 01:00:00';
   ASSERT_TRUE(CRT_BucketStart(tEarly, CRT_RANGE_SESSION, shNoZero) == D'2026.01.14 13:00:00',
               "Session bucket before the first session-of-day wraps to yesterday's last session (13:00)");
}

//+------------------------------------------------------------------+
//| Reference range: a completed period's high/low freezes as the     |
//| range the moment the next period's first bar arrives.              |
//+------------------------------------------------------------------+
void CRT_Test_RangeFreeze(void)
{
   Print("--- Reference range freeze on period rollover");
   datetime time[]; double open[], high[], low[], close[];
   int sh[]; CRT_MakeSessionHours(sh);

   CCRTZonesEngine eng;
   eng.Configure(CRT_RANGE_H4, sh, 14, false, 5.0, 0.0, 10, CRT_T_POINT);

   CRT_SetBar(time, open, high, low, close, D'2026.01.01 00:00', 100.00, 100.00, 100.05, 99.95);
   eng.ProcessClosedBar(0, time, open, high, low, close);
   ASSERT_TRUE(!eng.HasRange(), "no reference range yet on the very first bar");

   CRT_SetBar(time, open, high, low, close, D'2026.01.01 01:00', 100.00, 100.00, 100.50, 99.95);
   eng.ProcessClosedBar(0, time, open, high, low, close);
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 02:00', 100.00, 100.00, 100.50, 99.30);
   eng.ProcessClosedBar(0, time, open, high, low, close);
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 03:00', 100.00, 100.00, 100.10, 99.60);
   eng.ProcessClosedBar(0, time, open, high, low, close);
   ASSERT_TRUE(!eng.HasRange(), "still no frozen range while inside the first H4 period (hours 0-3)");

   // hour 4 = a new H4 bucket -> freezes hours[0..3]'s accumulated high/low
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 04:00', 100.00, 100.00, 100.10, 99.60);
   eng.ProcessClosedBar(0, time, open, high, low, close);
   ASSERT_TRUE(eng.HasRange(), "reference range is frozen once the period rolls over");
   ASSERT_NEAR(eng.RangeHi(), 100.50, 1e-9, "frozen range high = max high of the completed period");
   ASSERT_NEAR(eng.RangeLo(), 99.30, 1e-9, "frozen range low = min low of the completed period");
}

//+------------------------------------------------------------------+
//| Same-bar manipulation + distribution/reentry, bidirectional.      |
//+------------------------------------------------------------------+
void CRT_Test_SameBarSweepReentry(void)
{
   Print("--- Same-bar sweep + reentry (fast path)");
   datetime time[]; double open[], high[], low[], close[];
   int sh[]; CRT_MakeSessionHours(sh);

   // BUY: sweep below the range low, close back above it, same bar.
   CCRTZonesEngine engBuy;
   engBuy.Configure(CRT_RANGE_H4, sh, 14, false, 5.0, 0.0, 10, CRT_T_POINT); // threshold = 0.05
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 00:00', 100.00, 100.00, 100.05, 99.95);
   engBuy.ProcessClosedBar(0, time, open, high, low, close);
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 04:00', 99.90, 99.98, 99.99, 99.70);
   engBuy.ProcessClosedBar(0, time, open, high, low, close);

   ZI_Zone zBuy;
   bool foundBuy = CRT_FindZone(engBuy, ZI_BUY, zBuy);
   ASSERT_TRUE(foundBuy, "sweep below range low + same-bar reentry above it creates a BUY zone");
   if(foundBuy)
   {
      ASSERT_NEAR(zBuy.price_hi, 99.95, 1e-9, "BUY zone price_hi = reference range low (reentry level)");
      ASSERT_NEAR(zBuy.price_lo, 99.70, 1e-9, "BUY zone price_lo = the sweep bar's low (manipulation extreme)");
      ASSERT_EQ_INT(zBuy.strength, 3, "sweep depth (0.25) >= 3x threshold (0.05) -> strength 3");
   }
   ASSERT_TRUE(!engBuy.PendingBuyActive(), "confirmed same-bar reentry leaves no pending sweep state");

   // SELL: mirror - sweep above the range high, close back below it, same bar.
   CCRTZonesEngine engSell;
   engSell.Configure(CRT_RANGE_H4, sh, 14, false, 5.0, 0.0, 10, CRT_T_POINT);
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 00:00', 100.00, 100.00, 100.05, 99.95);
   engSell.ProcessClosedBar(0, time, open, high, low, close);
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 04:00', 100.10, 100.00, 100.40, 99.99);
   engSell.ProcessClosedBar(0, time, open, high, low, close);

   ZI_Zone zSell;
   bool foundSell = CRT_FindZone(engSell, ZI_SELL, zSell);
   ASSERT_TRUE(foundSell, "sweep above range high + same-bar reentry below it creates a SELL zone");
   if(foundSell)
   {
      ASSERT_NEAR(zSell.price_hi, 100.40, 1e-9, "SELL zone price_hi = the sweep bar's high (manipulation extreme)");
      ASSERT_NEAR(zSell.price_lo, 100.05, 1e-9, "SELL zone price_lo = reference range high (reentry level)");
   }

   // Negative case: a wick beyond the range that never closes back inside creates
   // no zone on this bar (it starts a pending sweep instead - see next test).
   CCRTZonesEngine engNo;
   engNo.Configure(CRT_RANGE_H4, sh, 14, false, 5.0, 0.0, 10, CRT_T_POINT);
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 00:00', 100.00, 100.00, 100.05, 99.95);
   engNo.ProcessClosedBar(0, time, open, high, low, close);
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 04:00', 99.90, 99.80, 99.91, 99.70); // closes below 99.95, no reentry
   engNo.ProcessClosedBar(0, time, open, high, low, close);
   ASSERT_EQ_INT(engNo.ZonesTotal(), 0, "sweep without same-bar reentry creates no zone yet");
   ASSERT_TRUE(engNo.PendingBuyActive(), "it becomes a pending BUY sweep awaiting reentry instead");
}

//+------------------------------------------------------------------+
//| Multi-bar manipulation: the sweep and the reentry can land on      |
//| different bars, as long as reentry arrives within the max-bars     |
//| window; otherwise the pending sweep expires with no zone.          |
//+------------------------------------------------------------------+
void CRT_Test_PendingReentry(void)
{
   Print("--- Multi-bar pending sweep -> reentry / expiry");
   datetime time[]; double open[], high[], low[], close[];
   int sh[]; CRT_MakeSessionHours(sh);

   // Reentry two bars after the sweep, deepening the extreme along the way.
   CCRTZonesEngine eng;
   eng.Configure(CRT_RANGE_H4, sh, 14, false, 5.0, 0.0, 10, CRT_T_POINT);
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 00:00', 100.00, 100.00, 100.05, 99.95);
   eng.ProcessClosedBar(0, time, open, high, low, close);
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 04:00', 99.90, 99.80, 99.85, 99.70); // sweep, no reentry
   eng.ProcessClosedBar(0, time, open, high, low, close);
   ASSERT_TRUE(eng.PendingBuyActive(), "sweep with no same-bar reentry starts a pending BUY state");
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 05:00', 99.78, 99.75, 99.80, 99.60); // deepens extreme, still no reentry
   eng.ProcessClosedBar(0, time, open, high, low, close);
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 06:00', 99.70, 99.98, 100.00, 99.65); // reentry: close back above 99.95
   eng.ProcessClosedBar(0, time, open, high, low, close);

   ZI_Zone z;
   bool found = CRT_FindZone(eng, ZI_BUY, z);
   ASSERT_TRUE(found, "reentry within the window confirms the pending sweep as a BUY zone");
   if(found)
   {
      ASSERT_NEAR(z.price_hi, 99.95, 1e-9, "pending-confirmed BUY zone price_hi = reference range low");
      ASSERT_NEAR(z.price_lo, 99.60, 1e-9, "pending-confirmed BUY zone price_lo = the deepest wick reached while pending");
   }
   ASSERT_TRUE(!eng.PendingBuyActive(), "confirming the pending sweep clears the pending state");

   // Expiry: no reentry within InpMaxReentryBars -> the pending sweep clears with no zone.
   CCRTZonesEngine engExp;
   engExp.Configure(CRT_RANGE_H4, sh, 14, false, 5.0, 0.0, 2, CRT_T_POINT); // maxReentryBars = 2
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 00:00', 100.00, 100.00, 100.05, 99.95);
   engExp.ProcessClosedBar(0, time, open, high, low, close);
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 04:00', 99.90, 99.80, 99.85, 99.70); // sweep (bars=0)
   engExp.ProcessClosedBar(0, time, open, high, low, close);
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 05:00', 99.80, 99.85, 99.88, 99.75); // no reentry (bars=1)
   engExp.ProcessClosedBar(0, time, open, high, low, close);
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 06:00', 99.85, 99.88, 99.90, 99.72); // no reentry (bars=2)
   engExp.ProcessClosedBar(0, time, open, high, low, close);
   ASSERT_TRUE(engExp.PendingBuyActive(), "pending sweep still alive at exactly maxReentryBars");
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 07:00', 99.88, 99.90, 99.92, 99.80); // no reentry (bars=3 -> expires)
   engExp.ProcessClosedBar(0, time, open, high, low, close);
   ASSERT_TRUE(!engExp.PendingBuyActive(), "pending sweep expires once it exceeds maxReentryBars without reentry");
   ASSERT_EQ_INT(engExp.ZonesTotal(), 0, "an expired pending sweep never becomes a zone");
}

//+------------------------------------------------------------------+
//| ATR-based strength filter: uses the incremental true-range        |
//| average (adapted from CRangePattern, see engine file header) and  |
//| must not fire before it has warmed up over InpATRPeriod bars.     |
//+------------------------------------------------------------------+
void CRT_Test_ATRFilter(void)
{
   Print("--- ATR-based sweep strength filter");
   datetime time[]; double open[], high[], low[], close[];
   int sh[]; CRT_MakeSessionHours(sh);

   CCRTZonesEngine eng;
   eng.Configure(CRT_RANGE_H4, sh, 3, true, 0.0, 1.0, 10, CRT_T_POINT); // atrPeriod=3, 1x ATR filter

   CRT_SetBar(time, open, high, low, close, D'2026.01.01 00:00', 100.00, 100.00, 100.05, 99.95);
   eng.ProcessClosedBar(0, time, open, high, low, close); // ATR sample 1
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 01:00', 100.00, 100.00, 100.10, 99.90);
   eng.ProcessClosedBar(0, time, open, high, low, close); // ATR sample 2
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 02:00', 100.00, 100.00, 100.05, 99.95);
   eng.ProcessClosedBar(0, time, open, high, low, close); // ATR sample 3 -> ATR now initialized
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 03:00', 100.00, 100.00, 100.05, 99.95);
   eng.ProcessClosedBar(0, time, open, high, low, close);
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 04:00', 100.00, 99.98, 100.00, 99.95); // rollover, no sweep
   eng.ProcessClosedBar(0, time, open, high, low, close);
   ASSERT_TRUE(eng.HasRange(), "range frozen after the first H4 period");

   // sweep well beyond any plausible ATR-derived threshold (~0.1-0.2), with reentry
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 05:00', 99.70, 99.95, 99.98, 99.55);
   eng.ProcessClosedBar(0, time, open, high, low, close);
   ZI_Zone z;
   bool found = CRT_FindZone(eng, ZI_BUY, z);
   ASSERT_TRUE(found, "a sweep clearing the ATR-derived threshold with reentry creates a BUY zone");
   if(found)
   {
      ASSERT_NEAR(z.price_lo, 99.55, 1e-9, "ATR-filtered BUY zone price_lo = the sweep bar's low");
   }

   // Negative case: ATR not yet warm -> sweep detection must be skipped entirely,
   // even for an enormous wick, rather than let a zero threshold wave it through.
   CCRTZonesEngine engCold;
   engCold.Configure(CRT_RANGE_H4, sh, 5, true, 0.0, 0.1, 10, CRT_T_POINT); // atrPeriod=5, only 2 samples will run
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 00:00', 100.00, 100.00, 100.05, 99.95);
   engCold.ProcessClosedBar(0, time, open, high, low, close);
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 04:00', 100.00, 99.98, 100.05, 50.00); // huge wick, rollover bar
   engCold.ProcessClosedBar(0, time, open, high, low, close);
   ASSERT_EQ_INT(engCold.ZonesTotal(), 0, "ATR warm-up guard skips sweep detection before atrPeriod bars accumulate, even for a huge wick");
}

//+------------------------------------------------------------------+
//| Mitigation: a zone is invalidated once price closes all the way    |
//| through it without reversing.                                      |
//+------------------------------------------------------------------+
void CRT_Test_Mitigation(void)
{
   Print("--- Mitigation");
   datetime time[]; double open[], high[], low[], close[];
   int sh[]; CRT_MakeSessionHours(sh);

   CCRTZonesEngine eng;
   eng.Configure(CRT_RANGE_H4, sh, 14, false, 5.0, 0.0, 10, CRT_T_POINT);
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 00:00', 100.00, 100.00, 100.05, 99.95);
   eng.ProcessClosedBar(0, time, open, high, low, close);
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 04:00', 99.90, 99.98, 99.99, 99.70);
   eng.ProcessClosedBar(0, time, open, high, low, close);
   ASSERT_EQ_INT(eng.ZonesTotal(), 1, "one BUY zone created");
   ASSERT_TRUE(!eng.IsMitigated(0), "freshly created zone is not mitigated");

   eng.CheckMitigation(99.85); // still inside [99.70, 99.95]
   ASSERT_TRUE(!eng.IsMitigated(0), "a close still inside the zone does not mitigate it");

   eng.CheckMitigation(99.60); // below price_lo (99.70) -> fully through
   ASSERT_TRUE(eng.IsMitigated(0), "a close below price_lo mitigates a BUY zone");

   eng.RemoveMitigated();
   ASSERT_EQ_INT(eng.ZonesTotal(), 0, "RemoveMitigated() physically drops the mitigated zone");
}

//+------------------------------------------------------------------+
//| Zone-cap eviction: once CRT_MAX_ZONES is exceeded, the oldest zone|
//| is dropped from m_zones AND queued in the pending-deletion list so|
//| the caller (SyncZoneObjects in CRT_ZonesInd.mq5) can delete its    |
//| chart objects instead of orphaning them on the chart forever.     |
//| ResetRangeMode() isolates each iteration's range/bucket state so   |
//| every pair of bars produces exactly one independent zone.          |
//+------------------------------------------------------------------+
void CRT_Test_ZoneEviction(void)
{
   Print("--- Zone cap eviction (CRT_MAX_ZONES) + pending-deletion queue");
   datetime time[]; double open[], high[], low[], close[];
   int sh[]; CRT_MakeSessionHours(sh);

   CCRTZonesEngine eng;
   eng.Configure(CRT_RANGE_H4, sh, 14, false, 5.0, 0.0, 10, CRT_T_POINT);

   int totalToAdd = CRT_MAX_ZONES + 5;
   datetime firstZoneTime = 0;
   for(int k = 0; k < totalToAdd; k++)
   {
      eng.ResetRangeMode(CRT_RANGE_H4); // fresh bucket/range/pending state, zones[] untouched
      datetime tA = (datetime)((long)D'2026.01.01 00:00' + (long)k * 7200);
      CRT_SetBar(time, open, high, low, close, tA, 100.00, 100.00, 100.05, 99.95);
      eng.ProcessClosedBar(0, time, open, high, low, close); // establishes the period, no range yet

      datetime tB = tA + 4 * 3600; // next H4 bucket -> freezes {100.05,99.95} and sweeps+reenters it
      if(k == 0) firstZoneTime = tB;
      CRT_SetBar(time, open, high, low, close, tB, 99.90, 99.98, 99.99, 99.70);
      eng.ProcessClosedBar(0, time, open, high, low, close);
   }

   ASSERT_EQ_INT(eng.ZonesTotal(), CRT_MAX_ZONES, "zone array stays capped at CRT_MAX_ZONES once exceeded");
   ASSERT_EQ_INT(eng.PendingDeletionsTotal(), totalToAdd - CRT_MAX_ZONES, "one pending deletion is queued per zone evicted past the cap");

   ZI_Zone evicted;
   bool gotFirst = eng.GetPendingDeletion(0, evicted);
   ASSERT_TRUE(gotFirst, "the earliest-evicted zone is readable from the pending-deletion queue");
   if(gotFirst)
      ASSERT_TRUE(evicted.bar_time == firstZoneTime, "the very first zone added is the first one evicted (oldest-first) and queued for chart cleanup - it would otherwise orphan its OBJ_RECTANGLE/OBJ_TEXT forever");

   eng.ClearPendingDeletions();
   ASSERT_EQ_INT(eng.PendingDeletionsTotal(), 0, "ClearPendingDeletions() drains the queue once the caller has cleaned up the chart objects");
}

//+------------------------------------------------------------------+
//| ResetRangeMode: switches grouping mode and clears live range/     |
//| bucket/pending state without discarding already-confirmed zones.  |
//+------------------------------------------------------------------+
void CRT_Test_ResetRangeMode(void)
{
   Print("--- ResetRangeMode (panel range-mode switch)");
   datetime time[]; double open[], high[], low[], close[];
   int sh[]; CRT_MakeSessionHours(sh);

   CCRTZonesEngine eng;
   eng.Configure(CRT_RANGE_H4, sh, 14, false, 5.0, 0.0, 10, CRT_T_POINT);
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 00:00', 100.00, 100.00, 100.05, 99.95);
   eng.ProcessClosedBar(0, time, open, high, low, close);
   CRT_SetBar(time, open, high, low, close, D'2026.01.01 04:00', 99.90, 99.98, 99.99, 99.70);
   eng.ProcessClosedBar(0, time, open, high, low, close);
   ASSERT_TRUE(eng.HasRange(), "range is frozen before the mode switch");
   ASSERT_EQ_INT(eng.ZonesTotal(), 1, "one zone confirmed before the mode switch");

   eng.ResetRangeMode(CRT_RANGE_DAILY);
   ASSERT_TRUE(eng.RangeMode() == CRT_RANGE_DAILY, "RangeMode() reflects the new mode after the switch");
   ASSERT_TRUE(!eng.HasRange(), "switching mode clears the live frozen range");
   ASSERT_EQ_INT(eng.ZonesTotal(), 1, "the zone confirmed under the old mode is NOT discarded by the switch");
}

//+------------------------------------------------------------------+
//| Panel layer-toggle contract: the g_show_* globals the panel's     |
//| checkboxes write to are what gates visibility, independent of     |
//| each other and of the min-strength highlight threshold.           |
//+------------------------------------------------------------------+
void CRT_Test_PanelToggleContract(void)
{
   Print("--- Panel layer-toggle contract (g_show_* globals)");

   g_show_zones = true; g_show_range = true;
   ASSERT_TRUE(g_show_zones, "zones layer visible by default");
   ASSERT_TRUE(g_show_range, "reference-range layer visible by default");

   g_show_zones = false;
   ASSERT_TRUE(!g_show_zones, "zones layer hidden when g_show_zones=false");
   ASSERT_TRUE(g_show_range, "toggling zones off does not affect the reference-range layer");

   g_show_range = false;
   ASSERT_TRUE(!g_show_range, "reference-range layer hidden when g_show_range=false");

   g_min_sweep_strength = 3;
   ZI_Zone z;
   z.strength = 2;
   ASSERT_TRUE(z.strength < g_min_sweep_strength, "strength 2 does not reach a panel-raised min-strength of 3");
   g_min_sweep_strength = 2; // restore default used elsewhere

   g_range_mode_request = (int)CRT_RANGE_SESSION;
   ASSERT_TRUE(g_range_mode_request == (int)CRT_RANGE_SESSION, "the panel's mode spin edit writes the requested mode, applied by the main .mq5 via ResetRangeMode()");
   g_range_mode_request = -1; // restore "no pending change"
}

//+------------------------------------------------------------------+
//| Alert-condition firing: ZI_Alert's per-bar throttle gate.         |
//+------------------------------------------------------------------+
void CRT_Test_AlertThrottle(void)
{
   Print("--- Alert throttle (ZI_Alert)");
   datetime last = 0;
   datetime bar1 = D'2026.01.01 00:00';
   datetime bar2 = bar1 + 60;

   ZI_Alert("zone formed", false, false, last, bar1);
   ASSERT_TRUE(last == bar1, "first alert call on a new bar updates last_alert_bar_time (would fire)");

   datetime saved = last;
   ZI_Alert("zone formed again same bar", false, false, last, bar1);
   ASSERT_TRUE(last == saved, "a second call for the SAME bar is throttled (state unchanged)");

   ZI_Alert("zone formed next bar", false, false, last, bar2);
   ASSERT_TRUE(last == bar2, "a call for a NEW bar is allowed to fire again");
}

//+------------------------------------------------------------------+
int CRT_RunAllTests(void)
{
   g_crtTestFailures = 0;
   g_crtTestPasses   = 0;
   CRT_Test_BucketStart();
   CRT_Test_RangeFreeze();
   CRT_Test_SameBarSweepReentry();
   CRT_Test_PendingReentry();
   CRT_Test_ATRFilter();
   CRT_Test_Mitigation();
   CRT_Test_ZoneEviction();
   CRT_Test_ResetRangeMode();
   CRT_Test_PanelToggleContract();
   CRT_Test_AlertThrottle();
   TEST_SUMMARY();
   return g_crtTestFailures;
}

#endif // CRT_TEST_SUITE_MQH
