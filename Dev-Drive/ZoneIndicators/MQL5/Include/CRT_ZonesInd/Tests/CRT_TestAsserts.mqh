//+------------------------------------------------------------------+
//| CRT_TestAsserts.mqh - minimal assert macros (pattern from         |
//| ZoneIndicators\MQL5\Include\SMC_ZonesInd\Tests\SMC_TestAsserts.mqh)|
//+------------------------------------------------------------------+
#ifndef CRT_TEST_ASSERTS_MQH
#define CRT_TEST_ASSERTS_MQH

int g_crtTestFailures = 0;
int g_crtTestPasses   = 0;

#define ASSERT_TRUE(cond,msg)      if(!(cond)){ g_crtTestFailures++; Print("FAIL: ",msg); } else { g_crtTestPasses++; Print("PASS: ",msg); }
#define ASSERT_EQ_INT(a,b,msg)     if((long)(a)!=(long)(b)){ g_crtTestFailures++; PrintFormat("FAIL: %s (got %d, want %d)",msg,(int)(a),(int)(b)); } else { g_crtTestPasses++; Print("PASS: ",msg); }
#define ASSERT_NEAR(a,b,tol,msg)   if(MathAbs((double)(a)-(double)(b))>(tol)){ g_crtTestFailures++; PrintFormat("FAIL: %s (got %.6f, want %.6f)",msg,(double)(a),(double)(b)); } else { g_crtTestPasses++; Print("PASS: ",msg); }
#define TEST_SUMMARY()             if(g_crtTestFailures==0) PrintFormat("=== ALL PASS (%d asserts) ===",g_crtTestPasses); else PrintFormat("=== %d FAILURES / %d asserts ===",g_crtTestFailures,g_crtTestPasses+g_crtTestFailures);

#endif // CRT_TEST_ASSERTS_MQH
