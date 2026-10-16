//+------------------------------------------------------------------+
//| SMC_TestAsserts.mqh - minimal assert macros (pattern from         |
//| H:\Dev-Drive\GridFib_EA\MQL5\Include\GridFib\Tests\TestAsserts.mqh)|
//+------------------------------------------------------------------+
#ifndef SMC_TEST_ASSERTS_MQH
#define SMC_TEST_ASSERTS_MQH

int g_smcTestFailures = 0;
int g_smcTestPasses   = 0;

#define ASSERT_TRUE(cond,msg)      if(!(cond)){ g_smcTestFailures++; Print("FAIL: ",msg); } else { g_smcTestPasses++; Print("PASS: ",msg); }
#define ASSERT_EQ_INT(a,b,msg)     if((long)(a)!=(long)(b)){ g_smcTestFailures++; PrintFormat("FAIL: %s (got %d, want %d)",msg,(int)(a),(int)(b)); } else { g_smcTestPasses++; Print("PASS: ",msg); }
#define ASSERT_NEAR(a,b,tol,msg)   if(MathAbs((double)(a)-(double)(b))>(tol)){ g_smcTestFailures++; PrintFormat("FAIL: %s (got %.6f, want %.6f)",msg,(double)(a),(double)(b)); } else { g_smcTestPasses++; Print("PASS: ",msg); }
#define TEST_SUMMARY()             if(g_smcTestFailures==0) PrintFormat("=== ALL PASS (%d asserts) ===",g_smcTestPasses); else PrintFormat("=== %d FAILURES / %d asserts ===",g_smcTestFailures,g_smcTestPasses+g_smcTestFailures);

#endif // SMC_TEST_ASSERTS_MQH
