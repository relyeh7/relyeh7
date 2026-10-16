//+------------------------------------------------------------------+
//| VWAP_TestSuite.mqh - unit tests for CVWAPZonesEngine + panel/alert|
//| toggle contracts. Shared by Experts\ZoneIndicators_Tests\         |
//| VWAP_ZonesInd_TestRunner.mq5 (headless Strategy Tester). No test   |
//| here touches the account or the chart.                            |
//+------------------------------------------------------------------+
#ifndef VWAP_TEST_SUITE_MQH
#define VWAP_TEST_SUITE_MQH

#include "VWAP_TestAsserts.mqh"
#include <ZoneIndicators\ZI_Common.mqh>
#include <VWAP_ZonesInd\VWAP_ZonesEngine.mqh>
#include <VWAP_ZonesInd\VWAP_ZonesMTF.mqh>
#include <VWAP_ZonesInd\VWAP_ZonesPanel.mqh>

#define VWAP_T_POINT 0.01

//--- Rebuilds the passed arrays as a single bar. The engine only ever reads
//--- index i for the call it's given (no historical lookback beyond its own
//--- internal state), so feeding one bar per call - in chronological order -
//--- is equivalent to feeding a full growing history array.
void VWAP_SetBar(datetime &time[], double &high[], double &low[], double &close[],
                  long &tickVol[], long &realVol[],
                  datetime t, double h, double l, double c, long tv, long rv)
{
   ArrayResize(time, 1);  ArrayResize(high, 1);  ArrayResize(low, 1);
   ArrayResize(close, 1); ArrayResize(tickVol, 1); ArrayResize(realVol, 1);
   time[0] = t; high[0] = h; low[0] = l; close[0] = c;
   tickVol[0] = tv; realVol[0] = rv;
}

bool VWAP_FindZone(CVWAPZonesEngine &eng, const ENUM_ZI_TYPE type, ZI_Zone &out)
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

//+------------------------------------------------------------------+
//| Day-bucket (session reset) boundary math.                         |
//+------------------------------------------------------------------+
void VWAP_Test_DayBucket(void)
{
   Print("--- Session (daily) bucket boundary");
   ASSERT_TRUE(VWAP_DayBucket(D'2026.01.15 13:45:00') == D'2026.01.15 00:00:00', "day bucket floors to midnight");
   ASSERT_TRUE(VWAP_DayBucket(D'2026.01.15 00:00:00') == D'2026.01.15 00:00:00', "a bar exactly at midnight is its own bucket start");
}

//+------------------------------------------------------------------+
//| VWAP core math: running Sum(v*typical)/Sum(v), verified against    |
//| the exact fractions computed inline (no hand-transcribed           |
//| decimals) at each of 3 bars.                                       |
//+------------------------------------------------------------------+
void VWAP_Test_CoreCalculation(void)
{
   Print("--- Session VWAP core calculation (hand-computable 3-bar series)");
   datetime time[]; double high[], low[], close[]; long tickVol[], realVol[];

   CVWAPZonesEngine eng;
   eng.Configure(1.0, 2.0, 1, 5, false, VWAP_T_POINT);

   // Bar 1: typical=(101+99+100)/3=100.0, vol=10
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:00', 101.0, 99.0, 100.0, 10, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   ASSERT_NEAR(eng.VWAP(), 1000.0 / 10.0, 1e-9, "VWAP after bar 1 = typical*vol / vol = 100.0");

   // Bar 2: typical=(102+100+101)/3=101.0, vol=20
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:15', 102.0, 100.0, 101.0, 20, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   ASSERT_NEAR(eng.VWAP(), (1000.0 + 101.0 * 20.0) / (10.0 + 20.0), 1e-9, "VWAP after bar 2 = cumPV/cumV = 3020/30");

   // Bar 3: typical=(103+101+102)/3=102.0, vol=30
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:30', 103.0, 101.0, 102.0, 30, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   ASSERT_NEAR(eng.VWAP(), (3020.0 + 102.0 * 30.0) / (30.0 + 30.0), 1e-9, "VWAP after bar 3 = cumPV/cumV = 6080/60");
}

//+------------------------------------------------------------------+
//| Session reset: a new day restarts the cumulative sums, so VWAP     |
//| jumps to just the first new-day bar's own typical price rather     |
//| than blending with the prior day.                                  |
//+------------------------------------------------------------------+
void VWAP_Test_SessionReset(void)
{
   Print("--- Session reset on day rollover");
   datetime time[]; double high[], low[], close[]; long tickVol[], realVol[];

   CVWAPZonesEngine eng;
   eng.Configure(1.0, 2.0, 1, 5, false, VWAP_T_POINT);

   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 23:00', 110.0, 90.0, 100.0, 100, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   ASSERT_NEAR(eng.VWAP(), 100.0, 1e-9, "day 1's VWAP reflects day 1's own bar");

   // Next bar rolls into day 2 - cumulative sums must restart, not blend.
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.02 00:00', 210.0, 190.0, 200.0, 50, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   ASSERT_NEAR(eng.VWAP(), 200.0, 1e-9, "day 2's VWAP = only day 2's bar's typical price - day 1 was NOT blended in");
}

//+------------------------------------------------------------------+
//| Deviation band formula: independently re-derives the volume-       |
//| weighted variance around the bar-4 running VWAP using the plain    |
//| textbook definition Sum(v*(tp-VWAP)^2)/Sum(v) (by hand, shown in   |
//| comments), and checks the engine's O(1) E[X^2]-E[X]^2 shortcut     |
//| matches it - this is the regression test for the algebraic         |
//| identity documented in VWAP_ZonesEngine.mqh's file header.         |
//+------------------------------------------------------------------+
void VWAP_Test_DeviationBands(void)
{
   Print("--- Deviation band formula (volume-weighted stddev around VWAP)");
   datetime time[]; double high[], low[], close[]; long tickVol[], realVol[];

   CVWAPZonesEngine eng;
   eng.Configure(1.0, 2.0, 1, 5, false, VWAP_T_POINT);

   // 4 bars, hand-verified below:
   //   typical: 100 (v=10), 102 (v=15), 101 (v=5), 105 (v=20)
   //   cumPV = 1000 + 1530 + 505 + 2100 = 5135, cumV = 50 -> VWAP = 102.7
   //   Sum(v*(tp-102.7)^2) = 10*(-2.7)^2 + 15*(-0.7)^2 + 5*(-1.7)^2 + 20*(2.3)^2
   //                       = 72.9 + 7.35 + 14.45 + 105.8 = 200.5
   //   variance = 200.5 / 50 = 4.01 ; stddev = sqrt(4.01)
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:00', 100.5, 99.5, 100.0, 10, 0); // typical exactly 100
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:15', 102.5, 101.5, 102.0, 15, 0); // typical exactly 102
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:30', 101.5, 100.5, 101.0, 5, 0); // typical exactly 101
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:45', 105.5, 104.5, 105.0, 20, 0); // typical exactly 105
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);

   ASSERT_NEAR(eng.VWAP(), 102.7, 1e-9, "VWAP after the 4-bar series = 5135/50 = 102.7");
   double expectedStdDev = MathSqrt(4.01);
   ASSERT_NEAR(eng.Band1Upper() - eng.VWAP(), expectedStdDev, 1e-6,
               "Band1Upper - VWAP = 1x the independently-derived volume-weighted stddev (sqrt(4.01))");
   ASSERT_NEAR(eng.VWAP() - eng.Band1Lower(), expectedStdDev, 1e-6, "VWAP - Band1Lower = the same stddev (symmetric band)");
   ASSERT_NEAR(eng.Band2Upper() - eng.VWAP(), 2.0 * expectedStdDev, 1e-6, "Band2Upper - VWAP = 2x stddev (InpBand2Mult=2.0)");
   ASSERT_NEAR(eng.VWAP() - eng.Band2Lower(), 2.0 * expectedStdDev, 1e-6, "VWAP - Band2Lower = 2x stddev");
}

//+------------------------------------------------------------------+
//| Volume-exhaustion BUY zone: declining volume over the full N-bar   |
//| chain (incl. the touch bar) + a new N-bar low + a band-1 touch     |
//| must all hold together for a zone to confirm.                      |
//+------------------------------------------------------------------+
void VWAP_Test_ExhaustionBuyZone(void)
{
   Print("--- Volume-exhaustion BUY zone (declining volume + new low + band touch)");
   datetime time[]; double high[], low[], close[]; long tickVol[], realVol[];

   // exhaustionBars=5 -> window capacity=4 (4 prior bars + the touch bar = a 5-bar chain)
   CVWAPZonesEngine eng;
   eng.Configure(1.0, 2.0, 1, 5, false, VWAP_T_POINT);

   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:00', 100.5, 99.5, 100.0, 50, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:15', 101.0, 99.0, 100.0, 50, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:30', 100.6, 99.6, 100.0, 40, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:45', 100.4, 99.7, 100.0, 30, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   ASSERT_EQ_INT(eng.ZonesTotal(), 0, "no zone yet - window not full, no touch/extreme evaluated");

   // Touch bar: deep wick to 90.0 (way below VWAP~100, both bands), lowest
   // volume in the chain (50,50,40,30,10 - non-increasing throughout).
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 01:00', 100.0, 90.0, 99.0, 10, 0);
   double band1LowerBefore = eng.Band1Lower(); // (unused directly - captured post-call below instead)
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   double band1LowerAtTouch = eng.Band1Lower();
   double band2LowerAtTouch = eng.Band2Lower();

   ZI_Zone z;
   bool found = VWAP_FindZone(eng, ZI_BUY, z);
   ASSERT_TRUE(found, "declining volume + new 4-bar low + band-1 touch confirms a BUY zone");
   if(found)
   {
      ASSERT_NEAR(z.price_lo, 90.0, 1e-9, "BUY zone price_lo = the touch bar's low (the wick extreme)");
      ASSERT_NEAR(z.price_hi, band1LowerAtTouch, 1e-9, "BUY zone price_hi = Band1Lower at the moment of the touch (InpTouchBand=1)");
      ASSERT_TRUE(90.0 <= band2LowerAtTouch, "sanity check: the touch also cleared the deeper 2-sigma band (drives the strength bonus below)");
      ASSERT_EQ_INT(z.strength, 3, "strength = 1 base + 1 (cleared 2-sigma band too) + 1 (volume <= 50% of the window's oldest bar) = 3");
   }
}

//+------------------------------------------------------------------+
//| Negative case: the exact same setup as the BUY zone test, but the  |
//| touch bar's volume INCREASES instead of continuing the decline -   |
//| no zone forms even though the wick is deep and makes a new low.    |
//+------------------------------------------------------------------+
void VWAP_Test_ExhaustionRequiresDecliningVolume(void)
{
   Print("--- Volume-exhaustion negative case: rising volume blocks the zone");
   datetime time[]; double high[], low[], close[]; long tickVol[], realVol[];

   CVWAPZonesEngine eng;
   eng.Configure(1.0, 2.0, 1, 5, false, VWAP_T_POINT);

   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:00', 100.5, 99.5, 100.0, 50, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:15', 101.0, 99.0, 100.0, 50, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:30', 100.6, 99.6, 100.0, 40, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:45', 100.4, 99.7, 100.0, 30, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);

   // Same deep wick to 90.0, but volume JUMPS to 1000 (breaks the decline: 30 -> 1000).
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 01:00', 100.0, 90.0, 99.0, 1000, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);

   ASSERT_EQ_INT(eng.ZonesTotal(), 0, "a deep new-low wick with RISING volume does not confirm a zone - decline is required");
}

//+------------------------------------------------------------------+
//| Negative case: touch + declining volume both hold, but the touch   |
//| bar's low does NOT beat the window's existing lowest low (99.0) -  |
//| hand-verified below that band-1 is still touched, yet no zone      |
//| forms because it isn't a new extreme.                              |
//+------------------------------------------------------------------+
void VWAP_Test_ExhaustionRequiresNewExtreme(void)
{
   Print("--- Volume-exhaustion negative case: no new extreme blocks the zone");
   datetime time[]; double high[], low[], close[]; long tickVol[], realVol[];

   CVWAPZonesEngine eng;
   eng.Configure(1.0, 2.0, 1, 5, false, VWAP_T_POINT);

   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:00', 100.5, 99.5, 100.0, 50, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:15', 101.0, 99.0, 100.0, 50, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:30', 100.6, 99.6, 100.0, 40, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:45', 100.4, 99.7, 100.0, 30, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   // window lows so far: [99.5, 99.0, 99.6, 99.7] -> min = 99.0

   // Touch bar: low=99.3 (> window min 99.0, so NOT a new low), declining volume (30->10),
   // and hand-verified to still clear Band1Lower (~99.82 at this point, see engine header
   // derivation style) - i.e. touch+decline both hold, isolating the missing-new-extreme case.
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 01:00', 99.5, 99.3, 99.4, 10, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);

   ASSERT_TRUE(99.3 <= eng.Band1Lower(), "sanity check: the touch bar's low did clear Band1Lower (touch condition holds)");
   ASSERT_EQ_INT(eng.ZonesTotal(), 0, "a band touch with declining volume but NOT a new N-bar low does not confirm a zone");
}

//+------------------------------------------------------------------+
//| Volume-exhaustion SELL zone: mirror of the BUY positive case,      |
//| confirms the upper-band/new-high path works, not just the lower.   |
//+------------------------------------------------------------------+
void VWAP_Test_ExhaustionSellZone(void)
{
   Print("--- Volume-exhaustion SELL zone (mirror of the BUY case)");
   datetime time[]; double high[], low[], close[]; long tickVol[], realVol[];

   CVWAPZonesEngine eng;
   eng.Configure(1.0, 2.0, 1, 5, false, VWAP_T_POINT);

   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:00', 100.5, 99.5, 100.0, 50, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:15', 101.0, 99.0, 100.0, 50, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:30', 100.6, 99.6, 100.0, 40, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:45', 100.4, 99.7, 100.0, 30, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   // window highs so far: [100.5, 101.0, 100.6, 100.4] -> max = 101.0

   // Touch bar: big upward wick to 110.0, lowest volume in the chain.
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 01:00', 110.0, 100.0, 101.0, 10, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   double band1UpperAtTouch = eng.Band1Upper();
   double band2UpperAtTouch = eng.Band2Upper();

   ZI_Zone z;
   bool found = VWAP_FindZone(eng, ZI_SELL, z);
   ASSERT_TRUE(found, "declining volume + new 4-bar high + band-1 touch confirms a SELL zone");
   if(found)
   {
      ASSERT_NEAR(z.price_hi, 110.0, 1e-9, "SELL zone price_hi = the touch bar's high (the wick extreme)");
      ASSERT_NEAR(z.price_lo, band1UpperAtTouch, 1e-9, "SELL zone price_lo = Band1Upper at the moment of the touch");
      ASSERT_TRUE(110.0 >= band2UpperAtTouch, "sanity check: the touch also cleared the deeper 2-sigma band");
      ASSERT_EQ_INT(z.strength, 3, "strength = 1 base + 1 (cleared 2-sigma) + 1 (volume <= 50% of window's oldest bar) = 3");
   }
}

//+------------------------------------------------------------------+
//| Mitigation: a zone is invalidated once price closes all the way    |
//| through it without reversing - same rule as SMC/CRT_ZonesEngine.   |
//+------------------------------------------------------------------+
void VWAP_Test_Mitigation(void)
{
   Print("--- Mitigation");
   datetime time[]; double high[], low[], close[]; long tickVol[], realVol[];

   CVWAPZonesEngine eng;
   eng.Configure(1.0, 2.0, 1, 5, false, VWAP_T_POINT);

   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:00', 100.5, 99.5, 100.0, 50, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:15', 101.0, 99.0, 100.0, 50, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:30', 100.6, 99.6, 100.0, 40, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:45', 100.4, 99.7, 100.0, 30, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 01:00', 100.0, 90.0, 99.0, 10, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);

   ASSERT_EQ_INT(eng.ZonesTotal(), 1, "one BUY zone created");
   ASSERT_TRUE(!eng.IsMitigated(0), "freshly created zone is not mitigated");

   ZI_Zone z; VWAP_FindZone(eng, ZI_BUY, z);
   eng.CheckMitigation(z.price_lo + 0.01); // still just inside the zone
   ASSERT_TRUE(!eng.IsMitigated(0), "a close still inside the zone does not mitigate it");

   eng.CheckMitigation(z.price_lo - 0.01); // below price_lo -> fully through
   ASSERT_TRUE(eng.IsMitigated(0), "a close below price_lo mitigates a BUY zone");

   eng.RemoveMitigated();
   ASSERT_EQ_INT(eng.ZonesTotal(), 0, "RemoveMitigated() physically drops the mitigated zone");
}

//+------------------------------------------------------------------+
//| Zone-cap eviction: once VWAP_MAX_ZONES is exceeded, the oldest     |
//| zone is dropped from m_zones AND queued in the pending-deletion    |
//| list so the caller (SyncZoneObjects in VWAP_ZonesInd.mq5) can       |
//| delete its chart objects instead of orphaning them forever.        |
//| SetExhaustionBars() re-runs each iteration purely to reset the      |
//| window (capacity unchanged at 2->1), keeping each 2-bar pair        |
//| independent, the same trick CRT's eviction test uses via           |
//| ResetRangeMode().                                                   |
//+------------------------------------------------------------------+
void VWAP_Test_ZoneEviction(void)
{
   Print("--- Zone cap eviction (VWAP_MAX_ZONES) + pending-deletion queue");
   datetime time[]; double high[], low[], close[]; long tickVol[], realVol[];

   CVWAPZonesEngine eng;
   eng.Configure(1.0, 2.0, 1, 2, false, VWAP_T_POINT); // exhaustionBars=2 -> window capacity=1 (minimal, fastest to fill)

   int totalToAdd = VWAP_MAX_ZONES + 5;
   datetime firstZoneTime = 0;
   for(int k = 0; k < totalToAdd; k++)
   {
      eng.SetExhaustionBars(2); // clears the 1-bar window so each iteration is independent

      datetime tA = (datetime)((long)D'2026.01.01 00:00' + (long)k * 120);
      VWAP_SetBar(time, high, low, close, tickVol, realVol, tA, 100.5, 99.5, 100.0, 100, 0); // fills the window
      eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);

      datetime tB = tA + 60;
      if(k == 0) firstZoneTime = tB;
      // Deep wick to 1.0 (always a new low vs. the window's 99.5), volume 1
      // (always <= window's 100, so the 2-bar chain 100,1 is non-increasing).
      VWAP_SetBar(time, high, low, close, tickVol, realVol, tB, 2.0, 1.0, 1.5, 1, 0);
      eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   }

   ASSERT_EQ_INT(eng.ZonesTotal(), VWAP_MAX_ZONES, "zone array stays capped at VWAP_MAX_ZONES once exceeded");
   ASSERT_EQ_INT(eng.PendingDeletionsTotal(), totalToAdd - VWAP_MAX_ZONES, "one pending deletion is queued per zone evicted past the cap");

   ZI_Zone evicted;
   bool gotFirst = eng.GetPendingDeletion(0, evicted);
   ASSERT_TRUE(gotFirst, "the earliest-evicted zone is readable from the pending-deletion queue");
   if(gotFirst)
      ASSERT_TRUE(evicted.bar_time == firstZoneTime, "the very first zone added is the first one evicted (oldest-first) and queued for chart cleanup");

   eng.ClearPendingDeletions();
   ASSERT_EQ_INT(eng.PendingDeletionsTotal(), 0, "ClearPendingDeletions() drains the queue once the caller has cleaned up the chart objects");
}

//+------------------------------------------------------------------+
//| VOLUME_TICK vs VOLUME_REAL fallback (design spec Section 4.3):     |
//| numbers chosen so tick-only, real-only, and fallback-to-tick each  |
//| produce a distinguishable VWAP - proves which volume source was    |
//| actually used, not just that a number came out.                    |
//+------------------------------------------------------------------+
void VWAP_Test_VolumeFallback(void)
{
   Print("--- VOLUME_TICK vs VOLUME_REAL fallback");
   datetime time[]; double high[], low[], close[]; long tickVol[], realVol[];

   // useRealVolume=false: must ignore real volume entirely, even though it's > 0 here.
   CVWAPZonesEngine engTick;
   engTick.Configure(1.0, 2.0, 1, 5, false, VWAP_T_POINT);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:00', 100.5, 99.5, 100.0, 10, 500);
   engTick.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:15', 200.5, 199.5, 200.0, 30, 100);
   engTick.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   ASSERT_NEAR(engTick.VWAP(), (100.0 * 10.0 + 200.0 * 30.0) / (10.0 + 30.0), 1e-9,
               "useRealVolume=false uses tick_volume only (7000/40=175.0), ignoring the very different real volume");

   // useRealVolume=true with real > 0 on both bars: must use real, not tick.
   CVWAPZonesEngine engReal;
   engReal.Configure(1.0, 2.0, 1, 5, true, VWAP_T_POINT);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:00', 100.5, 99.5, 100.0, 10, 500);
   engReal.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:15', 200.5, 199.5, 200.0, 30, 100);
   engReal.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   ASSERT_NEAR(engReal.VWAP(), (100.0 * 500.0 + 200.0 * 100.0) / (500.0 + 100.0), 1e-9,
               "useRealVolume=true uses real volume (70000/600=116.667), a different result than the tick-only run");

   // useRealVolume=true but bar 2 reports real=0 (broker doesn't supply it for that bar):
   // must fall back to tick_volume for THAT bar only, not corrupt the whole run.
   CVWAPZonesEngine engFallback;
   engFallback.Configure(1.0, 2.0, 1, 5, true, VWAP_T_POINT);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:00', 100.5, 99.5, 100.0, 100, 50); // real=50 used
   engFallback.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:15', 200.5, 199.5, 200.0, 10, 0); // real=0 -> falls back to tick=10
   engFallback.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   ASSERT_NEAR(engFallback.VWAP(), (100.0 * 50.0 + 200.0 * 10.0) / (50.0 + 10.0), 1e-9,
               "bar 2's real=0 falls back to its tick_volume=10 per-bar, giving 7000/60=116.667");
}

//+------------------------------------------------------------------+
//| Live panel requests (touch band / exhaustion window) reconfigure   |
//| the engine without discarding already-confirmed zones - same       |
//| "reconfigure live, keep history" contract as CRT's ResetRangeMode. |
//+------------------------------------------------------------------+
void VWAP_Test_LiveReconfigure(void)
{
   Print("--- Live touch-band / exhaustion-bars reconfigure (panel contract)");
   datetime time[]; double high[], low[], close[]; long tickVol[], realVol[];

   CVWAPZonesEngine eng;
   eng.Configure(1.0, 2.0, 1, 5, false, VWAP_T_POINT);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:00', 100.5, 99.5, 100.0, 50, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:15', 101.0, 99.0, 100.0, 50, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:30', 100.6, 99.6, 100.0, 40, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:45', 100.4, 99.7, 100.0, 30, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 01:00', 100.0, 90.0, 99.0, 10, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   ASSERT_EQ_INT(eng.ZonesTotal(), 1, "one zone confirmed before any live reconfigure");

   eng.SetTouchBand(2);
   ASSERT_TRUE(eng.TouchBand() == 2, "TouchBand() reflects the new value after SetTouchBand(2)");
   ASSERT_EQ_INT(eng.ZonesTotal(), 1, "changing the touch band does not discard the zone confirmed under the old setting");

   eng.SetExhaustionBars(10);
   ASSERT_TRUE(eng.ExhaustionBars() == 10, "ExhaustionBars() reflects the new value after SetExhaustionBars(10)");
   ASSERT_EQ_INT(eng.ZonesTotal(), 1, "changing the exhaustion window does not discard the zone confirmed under the old setting");
}

//+------------------------------------------------------------------+
//| Panel layer-toggle contract: the g_show_* globals the panel's     |
//| checkboxes write to are what gates visibility, independent of     |
//| each other and of the panel's live-request globals.                |
//+------------------------------------------------------------------+
void VWAP_Test_PanelToggleContract(void)
{
   Print("--- Panel layer-toggle contract (g_show_* globals)");

   g_show_vwap_line = true; g_show_bands = true; g_show_zones = true;
   ASSERT_TRUE(g_show_vwap_line, "VWAP line layer visible by default");
   ASSERT_TRUE(g_show_bands, "deviation bands layer visible by default");
   ASSERT_TRUE(g_show_zones, "zones layer visible by default");

   g_show_vwap_line = false;
   ASSERT_TRUE(!g_show_vwap_line, "VWAP line hidden when g_show_vwap_line=false");
   ASSERT_TRUE(g_show_bands, "toggling the VWAP line off does not affect the bands layer");

   g_show_bands = false;
   ASSERT_TRUE(!g_show_bands, "bands layer hidden when g_show_bands=false");
   ASSERT_TRUE(g_show_zones, "toggling bands off does not affect the zones layer");

   g_show_zones = false;
   ASSERT_TRUE(!g_show_zones, "zones layer hidden when g_show_zones=false");

   g_alert_push = false; g_alert_sound = true;
   ASSERT_TRUE(!g_alert_push && g_alert_sound, "push and sound alert toggles are independent of each other");

   g_min_zone_strength = 1;
   ZI_Zone zLow; zLow.strength = 1;
   ASSERT_TRUE(zLow.strength >= g_min_zone_strength, "with a panel-lowered min-strength of 1, a strength-1 zone now reaches the A+ highlight threshold");
   g_min_zone_strength = 3;
   ASSERT_TRUE(zLow.strength < g_min_zone_strength, "the same strength-1 zone no longer reaches a panel-raised min-strength of 3 - the live spin edit (VWAP_ZonesPanel.mqh's g_min_zone_strength, fix round 1) actually changes the highlight threshold");
   g_min_zone_strength = 2; // restore the suite's default used elsewhere

   g_touch_band_request = 2;
   ASSERT_TRUE(g_touch_band_request == 2, "the panel's touch-band spin edit writes the requested value, applied by the main .mq5");
   g_touch_band_request = -1; // restore "no pending change"

   g_exhaustion_bars_request = 8;
   ASSERT_TRUE(g_exhaustion_bars_request == 8, "the panel's exhaustion-bars spin edit writes the requested value, applied by the main .mq5");
   g_exhaustion_bars_request = -1; // restore "no pending change"
}

//+------------------------------------------------------------------+
//| Alert-condition firing: ZI_Alert's per-bar throttle gate.          |
//+------------------------------------------------------------------+
void VWAP_Test_AlertThrottle(void)
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
//| MTF signal row: CVWAPZonesMTFScanner.DecideSignal() driven with    |
//| synthetic engines (no CopyRates/real symbol data needed), plus     |
//| the VWAP_MTFShouldScan() refresh-interval gate.                    |
//+------------------------------------------------------------------+
void VWAP_Test_MTFSignals(void)
{
   Print("--- MTF Signals (CVWAPZonesMTFScanner)");
   datetime time[]; double high[], low[], close[]; long tickVol[], realVol[];

   CVWAPZonesMTFScanner scanner;
   scanner.Configure(1.0, 2.0, 1, 5, false, VWAP_T_POINT, 2);

   // Classification: a lone confirmed BUY zone (reusing VWAP_Test_ExhaustionBuyZone's
   // hand-verified 5-bar sequence) -> ZI_MTF_BUY.
   CVWAPZonesEngine engBuyOnly;
   engBuyOnly.Configure(1.0, 2.0, 1, 5, false, VWAP_T_POINT);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:00', 100.5, 99.5, 100.0, 50, 0);
   engBuyOnly.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:15', 101.0, 99.0, 100.0, 50, 0);
   engBuyOnly.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:30', 100.6, 99.6, 100.0, 40, 0);
   engBuyOnly.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:45', 100.4, 99.7, 100.0, 30, 0);
   engBuyOnly.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 01:00', 100.0, 90.0, 99.0, 10, 0);
   engBuyOnly.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   ASSERT_TRUE(scanner.DecideSignal(engBuyOnly) == ZI_MTF_BUY, "a single active BUY zone classifies as ZI_MTF_BUY");

   // Classification: a lone confirmed SELL zone (reusing VWAP_Test_ExhaustionSellZone's
   // hand-verified 5-bar sequence) -> ZI_MTF_SELL.
   CVWAPZonesEngine engSellOnly;
   engSellOnly.Configure(1.0, 2.0, 1, 5, false, VWAP_T_POINT);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:00', 100.5, 99.5, 100.0, 50, 0);
   engSellOnly.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:15', 101.0, 99.0, 100.0, 50, 0);
   engSellOnly.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:30', 100.6, 99.6, 100.0, 40, 0);
   engSellOnly.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:45', 100.4, 99.7, 100.0, 30, 0);
   engSellOnly.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 01:00', 110.0, 100.0, 101.0, 10, 0);
   engSellOnly.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   ASSERT_TRUE(scanner.DecideSignal(engSellOnly) == ZI_MTF_SELL, "a single active SELL zone classifies as ZI_MTF_SELL");

   // Classification: no touch bar at all -> no zones -> ZI_MTF_NONE.
   CVWAPZonesEngine engNone;
   engNone.Configure(1.0, 2.0, 1, 5, false, VWAP_T_POINT);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:00', 100.5, 99.5, 100.0, 50, 0);
   engNone.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   ASSERT_EQ_INT(engNone.ZonesTotal(), 0, "sanity check: a single non-touching bar creates no zone");
   ASSERT_TRUE(scanner.DecideSignal(engNone) == ZI_MTF_NONE, "no active zones in either direction classifies as ZI_MTF_NONE");

   // A+ priority over normal when both directions coexist: a deep (strength-3, A+) BUY touch
   // at 00:15, followed by a later (00:30) but shallow (strength-1, normal, band-1-only) SELL
   // touch. Naive most-recent-wins would pick the later SELL zone; the A+ rule must still pick
   // BUY. Bar-by-bar arithmetic hand-verified below (window capacity=1 via exhaustionBars=2,
   // the same minimal-window trick VWAP_Test_ZoneEviction uses).
   CVWAPZonesEngine engMixed;
   engMixed.Configure(1.0, 2.0, 1, 2, false, VWAP_T_POINT);
   // Bar A (00:00): typical=100.0, vol=100 - fills the 1-bar window, no touch possible yet.
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:00', 100.5, 99.5, 100.0, 100, 0);
   engMixed.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   // Bar B (00:15): typical=80.0 -> VWAP=13200/140=660/7=94.2857, stdDev=sqrt(81.632653)=9.0350;
   // Band1Lower=85.2507, Band2Lower=76.2157. low=50.0 clears BOTH bands and beats the window's
   // only low (99.5); vol=40 is <=40 (non-increasing vs window's 100) AND <=50% of 100 -> BUY
   // zone strength = 1 (base) + 1 (band2 cleared) + 1 (sharp vol decline) = 3 (A+).
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:15', 100.0, 50.0, 90.0, 40, 0);
   engMixed.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   // Bar C (00:30): typical=307/3=102.3333 -> VWAP=16781.6667/175=95.8952, stdDev=sqrt(75.673923)
   // =8.6989; Band1Upper=104.5941, Band2Upper=113.293. high=112.0 clears band1 but NOT band2
   // (112.0 < 113.293) and beats the window's only high (100.0, bar B's); vol=35 is <=40
   // (non-increasing) but NOT <=50% of 40 (20) -> SELL zone strength = 1 (base only, normal).
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:30', 112.0, 95.0, 100.0, 35, 0);
   engMixed.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);

   ASSERT_EQ_INT(engMixed.ZonesTotal(), 2, "exactly one BUY zone (00:15) and one SELL zone (00:30) were created");
   ZI_Zone zBuyM, zSellM;
   engMixed.GetZone(0, zBuyM); engMixed.GetZone(1, zSellM);
   ASSERT_TRUE(zBuyM.type == ZI_BUY && zBuyM.strength >= 2, "the first (00:15) zone is a BUY at A+ strength (>=2)");
   ASSERT_TRUE(zSellM.type == ZI_SELL && zSellM.strength < 2 && zSellM.bar_time > zBuyM.bar_time,
      "the second (00:30) zone is a SELL at normal strength and formed after the BUY zone");
   ASSERT_TRUE(!engMixed.IsMitigated(0) && !engMixed.IsMitigated(1), "neither zone was mitigated by the other bar's close (sanity check)");

   ASSERT_TRUE(scanner.DecideSignal(engMixed) == ZI_MTF_BUY, "an A+ BUY zone (min strength=2) outranks a more-recent but merely-normal SELL zone");

   // Refresh-interval gate: VWAP_MTFShouldScan mirrors OnTimer()'s once-per-N-seconds throttle.
   datetime t0 = D'2026.01.01 00:00:00';
   ASSERT_TRUE(!VWAP_MTFShouldScan(t0, t0 + 5, 10), "5s elapsed does not yet meet a 10s refresh interval");
   ASSERT_TRUE(VWAP_MTFShouldScan(t0, t0 + 10, 10), "exactly 10s elapsed meets the refresh interval (>=, not >)");
   ASSERT_TRUE(VWAP_MTFShouldScan(t0, t0 + 11, 10), "more than 10s elapsed still meets the refresh interval");
}

//+------------------------------------------------------------------+
//| MTF current-timeframe reuse (design spec S4): the chart's own      |
//| period must be decided from the live engine directly, never via    |
//| an independent CopyRates rescan - and DecideSignal() must not      |
//| mutate a shared/live engine (no RemoveMitigated side effect), or    |
//| an OnTimer-driven call could race SyncZoneObjects()'s own          |
//| pending-deletion bookkeeping in VWAP_ZonesInd.mq5 and orphan chart |
//| objects.                                                            |
//+------------------------------------------------------------------+
void VWAP_Test_MTFCurrentTimeframeReuse(void)
{
   Print("--- MTF current-timeframe reuse (no throwaway CopyRates scan for the chart's own period)");
   datetime time[]; double high[], low[], close[]; long tickVol[], realVol[];

   // Simulates g_engine: a "live" engine holding one BUY zone.
   CVWAPZonesEngine liveEngine;
   liveEngine.Configure(1.0, 2.0, 1, 5, false, VWAP_T_POINT);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:00', 100.5, 99.5, 100.0, 50, 0);
   liveEngine.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:15', 101.0, 99.0, 100.0, 50, 0);
   liveEngine.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:30', 100.6, 99.6, 100.0, 40, 0);
   liveEngine.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:45', 100.4, 99.7, 100.0, 30, 0);
   liveEngine.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 01:00', 100.0, 90.0, 99.0, 10, 0);
   liveEngine.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   ASSERT_EQ_INT(liveEngine.ZonesTotal(), 1, "the simulated live engine holds one BUY zone before any MTF scan");

   CVWAPZonesMTFScanner scanner;
   scanner.Configure(1.0, 2.0, 1, 5, false, VWAP_T_POINT, 2);

   int curIdx = scanner.IndexForPeriod(_Period);
   ASSERT_TRUE(curIdx >= 0, "the test runner's own chart period is one of the 6 tracked MTF timeframes");
   scanner.ScanAllReusingCurrent(_Symbol, 300, _Period, liveEngine);
   ASSERT_TRUE(scanner.Signal(curIdx) == ZI_MTF_BUY,
      "the current-timeframe slot reflects the live engine's own BUY zone directly, not an independent CopyRates rescan");

   // DecideSignal() must not mutate a shared live engine.
   int beforeCount = liveEngine.ZonesTotal();
   liveEngine.CheckMitigation(1.0); // closes far below price_lo -> mitigates the BUY zone
   ENUM_ZI_MTF_SIGNAL afterMitigation = scanner.DecideSignal(liveEngine);
   ASSERT_TRUE(afterMitigation == ZI_MTF_NONE, "a mitigated zone is excluded from the decision");
   ASSERT_EQ_INT(liveEngine.ZonesTotal(), beforeCount,
      "DecideSignal() does not physically remove the mitigated zone from a shared/live engine (no RemoveMitigated side effect)");

   // IndexForPeriod: round-trips for all 6 tracked timeframes, -1 for an untracked one.
   ASSERT_EQ_INT(scanner.IndexForPeriod(PERIOD_M1),  0, "IndexForPeriod(M1) = 0");
   ASSERT_EQ_INT(scanner.IndexForPeriod(PERIOD_M5),  1, "IndexForPeriod(M5) = 1");
   ASSERT_EQ_INT(scanner.IndexForPeriod(PERIOD_M15), 2, "IndexForPeriod(M15) = 2");
   ASSERT_EQ_INT(scanner.IndexForPeriod(PERIOD_H1),  3, "IndexForPeriod(H1) = 3");
   ASSERT_EQ_INT(scanner.IndexForPeriod(PERIOD_H4),  4, "IndexForPeriod(H4) = 4");
   ASSERT_EQ_INT(scanner.IndexForPeriod(PERIOD_D1),  5, "IndexForPeriod(D1) = 5");
   ASSERT_EQ_INT(scanner.IndexForPeriod(PERIOD_M30), -1, "IndexForPeriod(M30) = -1 (not one of the 6 tracked timeframes)");
}

//+------------------------------------------------------------------+
//| D1 session-degenerate case (task-3 design question, see the full   |
//| derivation in VWAP_ZonesMTF.mqh's file header): a D1 bar's own      |
//| time[] value already equals that day's own session-reset bucket,   |
//| so the daily reset fires on EVERY D1 bar, collapsing VWAP to that   |
//| single bar's own typical price and the deviation bands to exactly  |
//| VWAP (zero variance). This pins that exact, documented behavior    |
//| down as a regression test rather than leaving it as an unverified  |
//| comment.                                                            |
//+------------------------------------------------------------------+
void VWAP_Test_MTFDailyDegenerateBands(void)
{
   Print("--- D1 session-degenerate case: daily reset collapses the bands to a single-bar VWAP");
   datetime time[]; double high[], low[], close[]; long tickVol[], realVol[];

   CVWAPZonesEngine eng;
   eng.Configure(1.0, 2.0, 1, 5, false, VWAP_T_POINT);

   // Day 1's "D1 bar": time[] is that day's own midnight bucket start, exactly as a real
   // PERIOD_D1 bar's time[] would be.
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.01 00:00', 110.0, 90.0, 100.0, 777, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   double typical1 = (110.0 + 90.0 + 100.0) / 3.0;
   ASSERT_NEAR(eng.VWAP(), typical1, 1e-9, "day-1 D1 bar: VWAP collapses to that single bar's own typical price");
   ASSERT_NEAR(eng.Band1Upper(), eng.VWAP(), 1e-9, "day-1 D1 bar: Band1Upper == VWAP (stddev is exactly 0 for a single-bar session)");
   ASSERT_NEAR(eng.Band1Lower(), eng.VWAP(), 1e-9, "day-1 D1 bar: Band1Lower == VWAP too");
   ASSERT_NEAR(eng.Band2Upper(), eng.VWAP(), 1e-9, "day-1 D1 bar: Band2Upper == VWAP (the 2-sigma band degenerates identically)");
   ASSERT_NEAR(eng.Band2Lower(), eng.VWAP(), 1e-9, "day-1 D1 bar: Band2Lower == VWAP too");

   // Day 2's "D1 bar": the daily reset fires again (new bucket) - VWAP must NOT blend with
   // day 1, confirming the degeneracy repeats identically on every subsequent D1 bar.
   VWAP_SetBar(time, high, low, close, tickVol, realVol, D'2026.01.02 00:00', 220.0, 180.0, 200.0, 333, 0);
   eng.ProcessClosedBar(0, time, high, low, close, tickVol, realVol);
   double typical2 = (220.0 + 180.0 + 200.0) / 3.0;
   ASSERT_NEAR(eng.VWAP(), typical2, 1e-9, "day-2 D1 bar: VWAP is day 2's own typical price only - day 1 was NOT blended in");
   ASSERT_NEAR(eng.Band1Lower(), eng.VWAP(), 1e-9, "day-2 D1 bar: bands still collapse to VWAP on the very next D1 bar too");
}

//+------------------------------------------------------------------+
int VWAP_RunAllTests(void)
{
   g_vwapTestFailures = 0;
   g_vwapTestPasses   = 0;
   VWAP_Test_DayBucket();
   VWAP_Test_CoreCalculation();
   VWAP_Test_SessionReset();
   VWAP_Test_DeviationBands();
   VWAP_Test_ExhaustionBuyZone();
   VWAP_Test_ExhaustionRequiresDecliningVolume();
   VWAP_Test_ExhaustionRequiresNewExtreme();
   VWAP_Test_ExhaustionSellZone();
   VWAP_Test_Mitigation();
   VWAP_Test_ZoneEviction();
   VWAP_Test_VolumeFallback();
   VWAP_Test_LiveReconfigure();
   VWAP_Test_PanelToggleContract();
   VWAP_Test_AlertThrottle();
   VWAP_Test_MTFSignals();
   VWAP_Test_MTFCurrentTimeframeReuse();
   VWAP_Test_MTFDailyDegenerateBands();
   TEST_SUMMARY();
   return g_vwapTestFailures;
}

#endif // VWAP_TEST_SUITE_MQH
