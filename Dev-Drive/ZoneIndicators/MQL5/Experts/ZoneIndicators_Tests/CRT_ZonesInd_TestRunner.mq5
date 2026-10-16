//+------------------------------------------------------------------+
//|                                    CRT_ZonesInd_TestRunner.mq5    |
//| Headless test runner: run it in the Strategy Tester (any short   |
//| date range) and read PASS/FAIL lines from the agent log. All      |
//| assertions run in OnInit against synthetic bar arrays - no        |
//| account/chart access, no CAppDialog objects created. The first    |
//| tick ends the test.                                                |
//| Pattern: ZoneIndicators\MQL5\Experts\ZoneIndicators_Tests\         |
//|          SMC_ZonesInd_TestRunner.mq5                               |
//+------------------------------------------------------------------+
#property version "1.00"

#include <CRT_ZonesInd\Tests\CRT_TestSuite.mqh>

int g_failures = 0;

int OnInit()
{
   g_failures = CRT_RunAllTests();
   PrintFormat("CRT_ZonesInd_TestRunner: %d failures", g_failures);
   // A failing suite must fail the tester run itself, so run_backtest.ps1 (and a
   // human skimming the log) cannot mistake it for a green pass.
   return (g_failures == 0) ? INIT_SUCCEEDED : INIT_FAILED;
}

void OnTick()
{
   ExpertRemove(); // one tick is enough: ends the tester run
}
