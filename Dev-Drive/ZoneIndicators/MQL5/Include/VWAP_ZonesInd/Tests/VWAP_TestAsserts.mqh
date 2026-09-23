//+------------------------------------------------------------------+
//| VWAP_TestAsserts.mqh - minimal assert macros (pattern from        |
//| ZoneIndicators\MQL5\Include\CRT_ZonesInd\Tests\CRT_TestAsserts.mqh)|
//+------------------------------------------------------------------+
#ifndef VWAP_TEST_ASSERTS_MQH
#define VWAP_TEST_ASSERTS_MQH

int g_vwapTestFailures = 0;
int g_vwapTestPasses   = 0;

#define ASSERT_TRUE(cond,msg)      if(!(cond)){ g_vwapTestFailures++; Print("FAIL: ",msg); } else { g_vwapTestPasses++; Print("PASS: ",msg); }
#define ASSERT_EQ_INT(a,b,msg)     if((long)(a)!=(long)(b)){ g_vwapTestFailures++; PrintFormat("FAIL: %s (got %d, want %d)",msg,(int)(a),(int)(b)); } else { g_vwapTestPasses++; Print("PASS: ",msg); }
#define ASSERT_NEAR(a,b,tol,msg)   if(MathAbs((double)(a)-(double)(b))>(tol)){ g_vwapTestFailures++; PrintFormat("FAIL: %s (got %.6f, want %.6f)",msg,(double)(a),(double)(b)); } else { g_vwapTestPasses++; Print("PASS: ",msg); }
#define TEST_SUMMARY()             if(g_vwapTestFailures==0) PrintFormat("=== ALL PASS (%d asserts) ===",g_vwapTestPasses); else PrintFormat("=== %d FAILURES / %d asserts ===",g_vwapTestFailures,g_vwapTestPasses+g_vwapTestFailures);

#endif // VWAP_TEST_ASSERTS_MQH
