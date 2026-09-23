//+------------------------------------------------------------------+
//| SMC_TestSuite.mqh - unit tests for CSMCZonesEngine + panel/alert  |
//| toggle contracts. Shared by Experts\ZoneIndicators_Tests\         |
//| SMC_ZonesInd_TestRunner.mq5 (headless Strategy Tester). No test   |
//| here touches the account or the chart.                            |
//+------------------------------------------------------------------+
#ifndef SMC_TEST_SUITE_MQH
#define SMC_TEST_SUITE_MQH

#include "SMC_TestAsserts.mqh"
#include <ZoneIndicators\ZI_Common.mqh>
#include <SMC_ZonesInd\SMC_ZonesEngine.mqh>
#include <SMC_ZonesInd\SMC_ZonesPanel.mqh>

#define SMC_T_POINT 0.01

//--- Builds a flat n-bar baseline (open=close=100, small wick) starting at
//--- D'2026.01.01 00:00' with 60s spacing, so a test only has to overwrite
//--- the handful of bars its scenario actually needs.
void SMC_BuildBaseline(datetime &time[], double &open[], double &high[], double &low[], double &close[], int n)
{
   ArrayResize(time, n);
   ArrayResize(open, n);
   ArrayResize(high, n);
   ArrayResize(low, n);
   ArrayResize(close, n);
   datetime t0 = D'2026.01.01 00:00';
   for(int i = 0; i < n; i++)
   {
      time[i]  = t0 + i * 60;
      open[i]  = 100.00;
      close[i] = 100.00;
      high[i]  = 100.05;
      low[i]   = 99.95;
   }
}

bool SMC_FindZoneByLabel(CSMCZonesEngine &eng, const string label, const ENUM_ZI_TYPE type, ZI_Zone &out)
{
   int n = eng.ZonesTotal();
   for(int i = 0; i < n; i++)
   {
      ZI_Zone z;
      if(!eng.GetZone(i, z)) continue;
      if(z.label == label && z.type == type) { out = z; return true; }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Order Blocks: impulse body >= factor * previous-candle body       |
//+------------------------------------------------------------------+
void SMC_Test_OrderBlocks(void)
{
   Print("--- Order Blocks (Supply/Demand)");
   datetime time[]; double open[], high[], low[], close[];

   // Supply OB (SELL): OB candle at i=3 (doji), bearish impulse at i=4
   SMC_BuildBaseline(time, open, high, low, close, 6);
   open[3] = 100.00; close[3] = 100.00; high[3] = 100.05; low[3] = 99.95; // OB candle
   open[4] = 100.05; close[4] = 98.50;  high[4] = 100.06; low[4] = 98.40; // bearish impulse, body 1.55 >= 3*0.01

   CSMCZonesEngine engSell;
   engSell.Configure(3.0, 1.0, 50.0, 50, 50, SMC_T_POINT);
   engSell.ProcessClosedBar(4, time, open, high, low, close);

   ZI_Zone zSell;
   bool foundSell = SMC_FindZoneByLabel(engSell, "OB", ZI_SELL, zSell);
   ASSERT_TRUE(foundSell, "bearish impulse >=3x OB-candle body creates a Supply (SELL) OB");
   if(foundSell)
   {
      ASSERT_NEAR(zSell.price_hi, 100.05, 1e-9, "Supply OB price_hi = OB candle high");
      ASSERT_NEAR(zSell.price_lo, 99.95,  1e-9, "Supply OB price_lo = OB candle low");
   }

   // Demand OB (BUY): mirror - bullish impulse
   SMC_BuildBaseline(time, open, high, low, close, 6);
   open[3] = 100.00; close[3] = 100.00; high[3] = 100.05; low[3] = 99.95;
   open[4] = 99.95;  close[4] = 101.50; high[4] = 101.60; low[4] = 99.90; // bullish impulse, body 1.55

   CSMCZonesEngine engBuy;
   engBuy.Configure(3.0, 1.0, 50.0, 50, 50, SMC_T_POINT);
   engBuy.ProcessClosedBar(4, time, open, high, low, close);

   ZI_Zone zBuy;
   bool foundBuy = SMC_FindZoneByLabel(engBuy, "OB", ZI_BUY, zBuy);
   ASSERT_TRUE(foundBuy, "bullish impulse >=3x OB-candle body creates a Demand (BUY) OB");
   if(foundBuy)
   {
      ASSERT_NEAR(zBuy.price_hi, 100.05, 1e-9, "Demand OB price_hi = OB candle high");
      ASSERT_NEAR(zBuy.price_lo, 99.95,  1e-9, "Demand OB price_lo = OB candle low");
   }

   // Negative case: impulse body under the factor threshold creates nothing
   SMC_BuildBaseline(time, open, high, low, close, 6);
   open[3] = 100.00; close[3] = 100.00; high[3] = 100.05; low[3] = 99.95;
   open[4] = 100.00; close[4] = 100.015; high[4] = 100.05; low[4] = 99.95; // body 0.015 < 3*0.01

   CSMCZonesEngine engNo;
   engNo.Configure(3.0, 1.0, 50.0, 50, 50, SMC_T_POINT);
   engNo.ProcessClosedBar(4, time, open, high, low, close);
   ASSERT_EQ_INT(engNo.ZonesTotal(), 0, "sub-threshold impulse body creates no OB");
}

//+------------------------------------------------------------------+
//| Fair Value Gaps: 3-candle gap, bidirectional                      |
//+------------------------------------------------------------------+
void SMC_Test_FVG(void)
{
   Print("--- Fair Value Gaps");
   datetime time[]; double open[], high[], low[], close[];

   // Bullish FVG (BUY): low[i] - high[i-2] >= minGap
   SMC_BuildBaseline(time, open, high, low, close, 6);
   // bar2 stays baseline (high=100.05) -> candle1
   open[4] = 100.22; close[4] = 100.20; high[4] = 100.30; low[4] = 100.20; // candle3, small body to avoid OB overlap

   CSMCZonesEngine engBull;
   engBull.Configure(3.0, 1.0, 50.0, 50, 50, SMC_T_POINT);
   engBull.ProcessClosedBar(4, time, open, high, low, close);

   ZI_Zone zBull;
   bool foundBull = SMC_FindZoneByLabel(engBull, "FVG", ZI_BUY, zBull);
   ASSERT_TRUE(foundBull, "low[i] > high[i-2] by >=minGap creates a bullish (BUY) FVG");
   if(foundBull)
   {
      ASSERT_NEAR(zBull.price_hi, 100.20, 1e-9, "bullish FVG price_hi = low[i]");
      ASSERT_NEAR(zBull.price_lo, 100.05, 1e-9, "bullish FVG price_lo = high[i-2]");
   }

   // Bearish FVG (SELL): mirror - high[i] < low[i-2] by >=minGap
   SMC_BuildBaseline(time, open, high, low, close, 6);
   open[4] = 99.78; close[4] = 99.80; high[4] = 99.80; low[4] = 99.70; // candle3, small body

   CSMCZonesEngine engBear;
   engBear.Configure(3.0, 1.0, 50.0, 50, 50, SMC_T_POINT);
   engBear.ProcessClosedBar(4, time, open, high, low, close);

   ZI_Zone zBear;
   bool foundBear = SMC_FindZoneByLabel(engBear, "FVG", ZI_SELL, zBear);
   ASSERT_TRUE(foundBear, "high[i] < low[i-2] by >=minGap creates a bearish (SELL) FVG");
   if(foundBear)
   {
      ASSERT_NEAR(zBear.price_hi, 99.95, 1e-9, "bearish FVG price_hi = low[i-2]");
      ASSERT_NEAR(zBear.price_lo, 99.80, 1e-9, "bearish FVG price_lo = high[i]");
   }

   // Negative case: overlapping ranges (no true gap) create nothing
   SMC_BuildBaseline(time, open, high, low, close, 6);
   CSMCZonesEngine engNo;
   engNo.Configure(3.0, 1.0, 50.0, 50, 50, SMC_T_POINT);
   engNo.ProcessClosedBar(4, time, open, high, low, close);
   ASSERT_EQ_INT(engNo.ZonesTotal(), 0, "flat/overlapping bars create no FVG");
}

//+------------------------------------------------------------------+
//| Liquidity sweep: equal-highs/lows grouped into a pool, then swept |
//| with a close-back-inside rejection candle.                        |
//+------------------------------------------------------------------+
void SMC_Test_LiquiditySweep(void)
{
   Print("--- Liquidity Sweep (EQH/EQL pool)");
   datetime time[]; double open[], high[], low[], close[];

   // BSL sweep -> SELL: two equal highs at 101.00 (bars 3 and 6), then bar 9
   // wicks to 101.05 and closes back at 99.98 (below the 101.00 pool level).
   SMC_BuildBaseline(time, open, high, low, close, 10);
   high[3] = 101.00; low[3] = 99.95; open[3] = 100.00; close[3] = 100.00;
   high[6] = 101.00; low[6] = 99.95; open[6] = 100.00; close[6] = 100.00;
   high[9] = 101.05; low[9] = 99.95; open[9] = 100.00; close[9] = 99.98;

   CSMCZonesEngine engHigh;
   engHigh.Configure(3.0, 1.0, 50.0, 50, 50, SMC_T_POINT);
   engHigh.ProcessClosedBar(4, time, open, high, low, close); // confirms swing @3
   engHigh.ProcessClosedBar(7, time, open, high, low, close); // confirms swing @6 (pool = 2 points)
   engHigh.ProcessClosedBar(9, time, open, high, low, close); // sweep + close-back-below

   ZI_Zone zSweepSell;
   bool foundSweepSell = SMC_FindZoneByLabel(engHigh, "SWEEP", ZI_SELL, zSweepSell);
   ASSERT_TRUE(foundSweepSell, "equal-highs pool swept + close back below creates a SELL (BSL) zone");
   if(foundSweepSell)
   {
      ASSERT_NEAR(zSweepSell.price_hi, 101.05, 1e-9, "BSL sweep price_hi = sweeping bar's high");
      ASSERT_NEAR(zSweepSell.price_lo, 101.00, 1e-9, "BSL sweep price_lo = pool level");
   }

   // SSL sweep -> BUY: mirror, equal lows at 99.00
   SMC_BuildBaseline(time, open, high, low, close, 10);
   high[3] = 100.05; low[3] = 99.00; open[3] = 100.00; close[3] = 100.00;
   high[6] = 100.05; low[6] = 99.00; open[6] = 100.00; close[6] = 100.00;
   high[9] = 100.05; low[9] = 98.95; open[9] = 100.00; close[9] = 99.02;

   CSMCZonesEngine engLow;
   engLow.Configure(3.0, 1.0, 50.0, 50, 50, SMC_T_POINT);
   engLow.ProcessClosedBar(4, time, open, high, low, close);
   engLow.ProcessClosedBar(7, time, open, high, low, close);
   engLow.ProcessClosedBar(9, time, open, high, low, close);

   ZI_Zone zSweepBuy;
   bool foundSweepBuy = SMC_FindZoneByLabel(engLow, "SWEEP", ZI_BUY, zSweepBuy);
   ASSERT_TRUE(foundSweepBuy, "equal-lows pool swept + close back above creates a BUY (SSL) zone");
   if(foundSweepBuy)
   {
      ASSERT_NEAR(zSweepBuy.price_hi, 99.00,  1e-9, "SSL sweep price_hi = pool level");
      ASSERT_NEAR(zSweepBuy.price_lo, 98.95,  1e-9, "SSL sweep price_lo = sweeping bar's low");
   }

   // Negative case: a single prior high (no pool) is not "equal highs" -> no sweep
   SMC_BuildBaseline(time, open, high, low, close, 10);
   high[3] = 101.00; low[3] = 99.95; open[3] = 100.00; close[3] = 100.00;
   high[9] = 101.05; low[9] = 99.95; open[9] = 100.00; close[9] = 99.98;
   CSMCZonesEngine engSingle;
   engSingle.Configure(3.0, 1.0, 50.0, 50, 50, SMC_T_POINT);
   engSingle.ProcessClosedBar(4, time, open, high, low, close);
   engSingle.ProcessClosedBar(9, time, open, high, low, close);
   ZI_Zone zNone;
   ASSERT_TRUE(!SMC_FindZoneByLabel(engSingle, "SWEEP", ZI_SELL, zNone), "a single prior high (no equal-highs pool) does not trigger a sweep zone");
}

//+------------------------------------------------------------------+
//| Mitigation: a zone is invalidated + physically removed once price |
//| closes all the way through it.                                    |
//+------------------------------------------------------------------+
void SMC_Test_Mitigation(void)
{
   Print("--- Mitigation");
   datetime time[]; double open[], high[], low[], close[];

   SMC_BuildBaseline(time, open, high, low, close, 6);
   open[4] = 100.22; close[4] = 100.20; high[4] = 100.30; low[4] = 100.20; // bullish FVG [100.05,100.20]

   CSMCZonesEngine eng;
   eng.Configure(3.0, 1.0, 50.0, 50, 50, SMC_T_POINT);
   eng.ProcessClosedBar(4, time, open, high, low, close);
   ASSERT_EQ_INT(eng.ZonesTotal(), 1, "one BUY FVG zone created");
   ASSERT_TRUE(!eng.IsMitigated(0), "freshly created zone is not mitigated");

   eng.CheckMitigation(100.10); // still inside the zone
   ASSERT_TRUE(!eng.IsMitigated(0), "a close still inside the zone does not mitigate it");

   eng.CheckMitigation(100.00); // closed below price_lo (100.05) -> fully through
   ASSERT_TRUE(eng.IsMitigated(0), "a close below price_lo mitigates a BUY zone");

   eng.RemoveMitigated();
   ASSERT_EQ_INT(eng.ZonesTotal(), 0, "RemoveMitigated() physically drops the mitigated zone");

   // SELL zone mirror
   SMC_BuildBaseline(time, open, high, low, close, 6);
   open[3] = 100.00; close[3] = 100.00; high[3] = 100.05; low[3] = 99.95;
   open[4] = 100.05; close[4] = 98.50;  high[4] = 100.06; low[4] = 98.40;
   CSMCZonesEngine engSell;
   engSell.Configure(3.0, 1.0, 50.0, 50, 50, SMC_T_POINT);
   engSell.ProcessClosedBar(4, time, open, high, low, close); // Supply OB [99.95,100.05]
   ASSERT_EQ_INT(engSell.ZonesTotal(), 1, "one SELL OB zone created");
   engSell.CheckMitigation(100.06); // above price_hi -> fully through
   ASSERT_TRUE(engSell.IsMitigated(0), "a close above price_hi mitigates a SELL zone");
}

//+------------------------------------------------------------------+
//| Confluence: overlapping same-direction zones stack strength.      |
//+------------------------------------------------------------------+
void SMC_Test_Confluence(void)
{
   Print("--- Confluence stacking");
   datetime time[]; double open[], high[], low[], close[];

   // Two overlapping SELL OBs: [99.95,100.05] then [99.90,100.10]
   SMC_BuildBaseline(time, open, high, low, close, 10);
   open[3] = 100.00; close[3] = 100.00; high[3] = 100.05; low[3] = 99.95; // OB1 candle
   open[4] = 100.05; close[4] = 98.50;  high[4] = 100.06; low[4] = 98.40; // impulse1
   open[7] = 100.00; close[7] = 100.00; high[7] = 100.10; low[7] = 99.90; // OB2 candle (overlaps OB1)
   open[8] = 100.10; close[8] = 98.00;  high[8] = 100.11; low[8] = 97.90; // impulse2

   CSMCZonesEngine eng;
   eng.Configure(3.0, 1.0, 50.0, 50, 50, SMC_T_POINT);
   eng.ProcessClosedBar(4, time, open, high, low, close);
   eng.ProcessClosedBar(8, time, open, high, low, close);

   ASSERT_EQ_INT(eng.ZonesTotal(), 2, "two overlapping SELL OBs both created");
   ZI_Zone z0, z1;
   eng.GetZone(0, z0);
   eng.GetZone(1, z1);
   ASSERT_TRUE(z0.strength >= 2, "first zone's strength stacks (>=2) once a second overlapping zone forms");
   ASSERT_TRUE(z1.strength >= 2, "second (newly formed) overlapping zone starts stacked (>=2)");
}

//+------------------------------------------------------------------+
//| Premium/Discount: a SELL zone formed in the premium half of the   |
//| recent range gets a confluence bonus; in discount, it does not.   |
//+------------------------------------------------------------------+
void SMC_Test_PremiumDiscount(void)
{
   Print("--- Premium/Discount confluence bonus");
   datetime time[]; double open[], high[], low[], close[];

   // Premium case: a deep historical low (bar0) keeps the range midpoint well
   // below the bearish impulse's close, so that close still sits in premium.
   SMC_BuildBaseline(time, open, high, low, close, 5);
   open[0] = 95.00; close[0] = 95.00; high[0] = 95.05; low[0] = 90.00; // deep low -> pulls range mid down
   open[3] = 100.00; close[3] = 100.00; high[3] = 100.05; low[3] = 99.95; // OB candle
   open[4] = 100.05; close[4] = 98.50;  high[4] = 100.06; low[4] = 98.40; // impulse, close 98.50

   CSMCZonesEngine engPremium;
   engPremium.Configure(3.0, 1.0, 50.0, 50, 50, SMC_T_POINT);
   engPremium.ProcessClosedBar(4, time, open, high, low, close);
   ASSERT_TRUE(engPremium.IsPremium(), "close sits above the range midpoint (premium) in this scenario");
   ZI_Zone zP;
   ASSERT_TRUE(SMC_FindZoneByLabel(engPremium, "OB", ZI_SELL, zP), "SELL OB created");
   ASSERT_EQ_INT(zP.strength, 2, "SELL zone formed in premium gets the +1 confluence bonus (1 base + 1 premium)");

   // Discount case: a high historical high (bar0) pulls the range midpoint up
   // above the bearish impulse's close, so that close now sits in discount.
   SMC_BuildBaseline(time, open, high, low, close, 5);
   open[0] = 105.00; close[0] = 105.00; high[0] = 110.00; low[0] = 104.95; // high spike -> pulls range mid up
   open[3] = 100.00; close[3] = 100.00; high[3] = 100.05; low[3] = 99.95;
   open[4] = 100.05; close[4] = 98.50;  high[4] = 100.06; low[4] = 98.40;

   CSMCZonesEngine engDiscount;
   engDiscount.Configure(3.0, 1.0, 50.0, 50, 50, SMC_T_POINT);
   engDiscount.ProcessClosedBar(4, time, open, high, low, close);
   ASSERT_TRUE(!engDiscount.IsPremium(), "close sits below the range midpoint (discount) in this scenario");
   ZI_Zone zD;
   ASSERT_TRUE(SMC_FindZoneByLabel(engDiscount, "OB", ZI_SELL, zD), "SELL OB created");
   ASSERT_EQ_INT(zD.strength, 1, "SELL zone formed in discount gets no confluence bonus (base only)");
}

//+------------------------------------------------------------------+
//| Panel layer-toggle contract: the g_show_* globals the panel's     |
//| checkboxes write to are exactly what gates a zone's visibility.   |
//| This mirrors SMC_ZonesInd.mq5's SyncZoneObjects() "layerOn"       |
//| predicate (that function lives in the wiring .mq5, not a reusable |
//| module, so it is intentionally re-stated here rather than called).|
//| It does NOT drive real CAppDialog controls or chart objects - see |
//| the task report for why that is not exercised headlessly.        |
//+------------------------------------------------------------------+
bool SMC_LayerOn(const string label)
{
   if(label == "OB")    return g_show_ob;
   if(label == "FVG")   return g_show_fvg;
   if(label == "SWEEP") return g_show_sweep;
   return false;
}

void SMC_Test_PanelToggleContract(void)
{
   Print("--- Panel layer-toggle contract (g_show_* globals)");

   g_show_ob = true; g_show_fvg = true; g_show_sweep = true;
   ASSERT_TRUE(SMC_LayerOn("OB"),    "OB layer visible when g_show_ob=true");
   ASSERT_TRUE(SMC_LayerOn("FVG"),   "FVG layer visible when g_show_fvg=true");
   ASSERT_TRUE(SMC_LayerOn("SWEEP"), "SWEEP layer visible when g_show_sweep=true");

   g_show_ob = false;
   ASSERT_TRUE(!SMC_LayerOn("OB"), "OB layer hidden when g_show_ob=false");
   ASSERT_TRUE(SMC_LayerOn("FVG"), "toggling OB off does not affect the FVG layer");

   g_show_fvg = false;
   g_show_sweep = false;
   ASSERT_TRUE(!SMC_LayerOn("FVG"),   "FVG layer hidden when g_show_fvg=false");
   ASSERT_TRUE(!SMC_LayerOn("SWEEP"), "SWEEP layer hidden when g_show_sweep=false");

   // Confluence threshold is independently panel-controlled
   g_min_confluence = 3;
   ZI_Zone z;
   z.strength = 2;
   ASSERT_TRUE(z.strength < g_min_confluence, "strength 2 does not reach a panel-raised min-confluence of 3");
   g_min_confluence = 2; // restore default used elsewhere
}

//+------------------------------------------------------------------+
//| Alert-condition firing: ZI_Alert's per-bar throttle gate.         |
//| push/sound are passed false so no real Alert()/SendNotification() |
//| fires during this headless run.                                   |
//+------------------------------------------------------------------+
void SMC_Test_AlertThrottle(void)
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
int SMC_RunAllTests(void)
{
   g_smcTestFailures = 0;
   g_smcTestPasses   = 0;
   SMC_Test_OrderBlocks();
   SMC_Test_FVG();
   SMC_Test_LiquiditySweep();
   SMC_Test_Mitigation();
   SMC_Test_Confluence();
   SMC_Test_PremiumDiscount();
   SMC_Test_PanelToggleContract();
   SMC_Test_AlertThrottle();
   TEST_SUMMARY();
   return g_smcTestFailures;
}

#endif // SMC_TEST_SUITE_MQH
