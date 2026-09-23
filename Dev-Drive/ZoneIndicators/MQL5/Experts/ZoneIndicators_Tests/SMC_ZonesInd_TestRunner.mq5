//+------------------------------------------------------------------+
//|                                    SMC_ZonesInd_TestRunner.mq5    |
//| Headless test runner: run it in the Strategy Tester (any short   |
//| date range) and read PASS/FAIL lines from the agent log. All      |
//| assertions run in OnInit against synthetic bar arrays - no        |
//| account/chart access, no CAppDialog objects created. The first    |
//| tick ends the test.                                                |
//| Pattern: H:\Dev-Drive\GridFib_EA\MQL5\Experts\GridFib\             |
//|          GridFib_TestRunner.mq5                                    |
//+------------------------------------------------------------------+
#property version "1.00"

#include <SMC_ZonesInd\Tests\SMC_TestSuite.mqh>

int g_failures = 0;

int OnInit()
{
   g_failures = SMC_RunAllTests();
   PrintFormat("SMC_ZonesInd_TestRunner: %d failures", g_failures);
   // A failing suite must fail the tester run itself, so run_backtest.ps1 (and a
   // human skimming the log) cannot mistake it for a green pass.
   return (g_failures == 0) ? INIT_SUCCEEDED : INIT_FAILED;
}

void OnTick()
{
   ExpertRemove(); // one tick is enough: ends the tester run
}
