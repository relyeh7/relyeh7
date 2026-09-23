//+------------------------------------------------------------------+
//|                                                 SMC_ZonesInd.mq5 |
//| Bidirectional Smart Money Concepts zones: Supply/Demand Order     |
//| Blocks, Bullish/Bearish Fair Value Gaps, EQH/EQL liquidity sweep,  |
//| Premium/Discount filter with stacking confluence. Detection-only  |
//| indicator - no order execution.                                   |
//|                                                                    |
//| Basado en mql5.com/es/articles/15899 (Niquel Mendoza) - Order      |
//|   Blocks; mql5.com/es/articles/18669 (Eugene Mmene) - Fair Value   |
//|   Gaps; mql5.com/es/articles/18379 (lynnchris) - liquidity sweep.  |
//| Panel pattern copied from H:\Dev-Drive\SMC\SMC_Indicator.mq5.      |
//+------------------------------------------------------------------+
#property copyright   "Zone Indicators Suite"
#property link        ""
#property version     "1.00"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

#include <ZoneIndicators\ZI_Common.mqh>
#include <SMC_ZonesInd\SMC_ZonesEngine.mqh>
#include <SMC_ZonesInd\SMC_ZonesPanel.mqh>

//+------------------------------------------------------------------+
//| Inputs                                                            |
//+------------------------------------------------------------------+
input string Section_SMC          = "==== SMC Detection ====";  // SMC Detection
input double InpImpulseFactor     = 3.0;   // OB: impulse body >= factor * OB candle body
input double InpFVGMinPoints      = 1.0;   // FVG: minimum gap size (points)
input double InpEQTolerancePoints = 50.0;  // EQH/EQL: clustering tolerance (points)
input int    InpRangeLookbackBars = 50;    // Premium/Discount range lookback (bars)
input int    InpSwingLookbackBars = 50;    // Liquidity pool swing lookback (bars)

input string Section_Alerts    = "==== Alerts ====";  // Alerts
input bool   InpAlertPush      = true;    // Push Notification on New Zone / A+
input bool   InpAlertSound     = true;    // Sound Alert on New Zone / A+
input bool   InpAlertOnTouch   = false;   // Also Alert When an Existing Zone is Touched

input string Section_Panel     = "==== Control Panel ====";  // Control Panel
input bool   InpShowPanel      = true;    // Show Control Panel
input int    InpPanelCorner    = 0;       // Panel Anchor (0=UL,1=UR,2=LL,3=LR)
input int    InpPanelX         = 20;      // Panel X Offset (pixels)
input int    InpPanelY         = 20;      // Panel Y Offset (pixels)
input int    InpMinConfluence  = 2;       // Min Confluence for A+ Highlight (1-5)

input string Section_Layers    = "==== Zone Layers (default) ====";  // Zone Layers
input bool   InpShowOB         = true;    // Show Order Blocks
input bool   InpShowFVG        = true;    // Show Fair Value Gaps
input bool   InpShowSweep      = true;    // Show Liquidity Sweeps
input bool   InpShowPD         = true;    // Show Premium/Discount Line

input string Section_Colors    = "==== Colors ====";  // Colors
input color  InpColorBuy           = C'20,150,130';  // Buy Zone Color
input color  InpColorSell          = C'180,40,40';   // Sell Zone Color
input color  InpColorHighlightBuy  = clrLime;         // Buy Zone Color (A+ Confluence)
input color  InpColorHighlightSell = clrRed;          // Sell Zone Color (A+ Confluence)

//+------------------------------------------------------------------+
//| Globals                                                           |
//+------------------------------------------------------------------+
CSMCZonesEngine g_engine;
CSMCZonesPanel  ExtPanel;

datetime g_lastAlertNewZone    = 0;
datetime g_lastAlertConfluence = 0;
datetime g_lastAlertTouch      = 0;

//+------------------------------------------------------------------+
string ZoneObjName(const ZI_Zone &z)
{
   return StringFormat("ZI_SMC_%s_%s_%I64d", z.label, (z.type == ZI_BUY ? "BUY" : "SELL"), (long)z.bar_time);
}

void DeleteZoneObj(const string &name)
{
   ObjectDelete(0, name);
   ObjectDelete(0, name + "_txt");
}

color ZoneColor(const ENUM_ZI_TYPE type, const bool highlight)
{
   if(type == ZI_BUY)  return highlight ? InpColorHighlightBuy  : InpColorBuy;
   return highlight ? InpColorHighlightSell : InpColorSell;
}

void DrawOrUpdateZone(const string &name, const ZI_Zone &z)
{
   datetime t2 = TimeCurrent() + PeriodSeconds() * 5;
   bool isNew = (ObjectFind(0, name) < 0);
   if(isNew)
   {
      if(!ObjectCreate(0, name, OBJ_RECTANGLE, 0, z.bar_time, z.price_hi, t2, z.price_lo))
         return;
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_FILL, true);
   }
   else
   {
      ObjectMove(0, name, 1, t2, z.price_lo);
   }

   bool highlight = (z.strength >= g_min_confluence);
   color clr = ZoneColor(z.type, highlight);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, highlight ? 2 : 1);

   string txt = StringFormat("%s %s%s (%d)", z.label, (z.type == ZI_BUY ? "BUY" : "SELL"),
                              highlight ? " A+" : "", z.strength);
   string tname = name + "_txt";
   if(ObjectFind(0, tname) < 0)
   {
      ObjectCreate(0, tname, OBJ_TEXT, 0, z.bar_time, z.price_hi);
      ObjectSetInteger(0, tname, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, tname, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, tname, OBJPROP_FONTSIZE, 7);
   }
   ObjectSetString(0, tname, OBJPROP_TEXT, txt);
   ObjectSetInteger(0, tname, OBJPROP_COLOR, clr);
}

void DrawPDLine(void)
{
   string name  = "ZI_SMC_PD_Line";
   string tname = "ZI_SMC_PD_Line_txt";
   if(!g_show_pd)
   {
      ObjectDelete(0, name);
      ObjectDelete(0, tname);
      return;
   }
   double mid = g_engine.RangeMid();
   if(mid <= 0.0) return;

   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, mid);
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DOT);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clrSilver);
   }
   else
      ObjectSetDouble(0, name, OBJPROP_PRICE, mid);

   string txt = g_engine.IsPremium() ? "PREMIUM" : "DISCOUNT";
   if(ObjectFind(0, tname) < 0)
   {
      ObjectCreate(0, tname, OBJ_TEXT, 0, TimeCurrent(), mid);
      ObjectSetInteger(0, tname, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, tname, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, tname, OBJPROP_FONTSIZE, 7);
      ObjectSetInteger(0, tname, OBJPROP_COLOR, clrSilver);
   }
   else
      ObjectMove(0, tname, 0, TimeCurrent(), mid);
   ObjectSetString(0, tname, OBJPROP_TEXT, txt);
}

//+------------------------------------------------------------------+
//| Reconciles chart objects with the engine's current zone list:     |
//| draws/updates active zones whose layer is enabled, deletes        |
//| objects for mitigated or hidden zones, then compacts the array.   |
//+------------------------------------------------------------------+
void SyncZoneObjects(void)
{
   int n = g_engine.ZonesTotal();
   for(int idx = 0; idx < n; idx++)
   {
      ZI_Zone z;
      if(!g_engine.GetZone(idx, z)) continue;
      string name = ZoneObjName(z);
      bool layerOn = (z.label == "OB"    && g_show_ob)    ||
                     (z.label == "FVG"   && g_show_fvg)   ||
                     (z.label == "SWEEP" && g_show_sweep);
      if(g_engine.IsMitigated(idx) || !layerOn)
         DeleteZoneObj(name);
      else
         DrawOrUpdateZone(name, z);
   }
   g_engine.RemoveMitigated();
   DrawPDLine();
   g_panel_force_redraw = false;
}

void CheckTouchAlerts(void)
{
   if(!InpAlertOnTouch) return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(bid <= 0.0) return;

   int n = g_engine.ZonesTotal();
   for(int idx = 0; idx < n; idx++)
   {
      if(g_engine.IsMitigated(idx) || g_engine.WasTouched(idx)) continue;
      ZI_Zone z;
      if(!g_engine.GetZone(idx, z)) continue;
      if(bid >= z.price_lo && bid <= z.price_hi)
      {
         g_engine.MarkTouched(idx);
         string msg = StringFormat("%s %s zone touched: %s [%.5f-%.5f] strength=%d",
                                    _Symbol, (z.type == ZI_BUY ? "BUY" : "SELL"), z.label,
                                    z.price_lo, z.price_hi, z.strength);
         ZI_Alert(msg, g_alert_push, g_alert_sound, g_lastAlertTouch, iTime(_Symbol, _Period, 0));
      }
   }
}

//+------------------------------------------------------------------+
int OnInit()
{
   g_show_ob    = InpShowOB;
   g_show_fvg   = InpShowFVG;
   g_show_sweep = InpShowSweep;
   g_show_pd    = InpShowPD;
   g_min_confluence = (InpMinConfluence >= 1 && InpMinConfluence <= 5) ? InpMinConfluence : 2;
   g_alert_push  = InpAlertPush;
   g_alert_sound = InpAlertSound;
   g_panel_force_redraw = false;

   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(point <= 0.0) point = _Point;
   g_engine.Configure(InpImpulseFactor, InpFVGMinPoints, InpEQTolerancePoints,
                       InpRangeLookbackBars, InpSwingLookbackBars, point);

   g_lastAlertNewZone    = 0;
   g_lastAlertConfluence = 0;
   g_lastAlertTouch      = 0;

   ObjectsDeleteAll(0, "ZI_SMC_");

   if(InpShowPanel)
   {
      ChartSetInteger(0, CHART_EVENT_MOUSE_MOVE, true);
      if(!ExtPanel.CreateAt(0, 0, InpPanelCorner, InpPanelX, InpPanelY))
      {
         Print("SMC_ZonesInd: failed to create control panel");
         return INIT_FAILED;
      }
      ExtPanel.Run();
      EventSetTimer(1);
   }

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(InpShowPanel)
   {
      EventKillTimer();
      ExtPanel.Destroy(reason);
   }
   ObjectsDeleteAll(0, "ZI_SMC_");
}

//+------------------------------------------------------------------+
void OnTimer()
{
   if(InpShowPanel) ExtPanel.Refresh();
}

//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
   if(InpShowPanel)
      ExtPanel.ChartEvent(id, lparam, dparam, sparam);
}

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                 const int prev_calculated,
                 const datetime &time[],
                 const double &open[],
                 const double &high[],
                 const double &low[],
                 const double &close[],
                 const long &tick_volume[],
                 const long &volume[],
                 const int &spread[])
{
   if(rates_total < 6) return 0;

   bool isHistoryReplay = (prev_calculated == 0);
   int limit = isHistoryReplay ? 3 : prev_calculated - 1;
   if(limit < 3) limit = 3;

   int beforeCount = g_engine.ZonesTotal();
   for(int i = limit; i < rates_total - 1; i++)
      g_engine.ProcessClosedBar(i, time, open, high, low, close);
   int afterCount = g_engine.ZonesTotal();

   if(!isHistoryReplay && afterCount > beforeCount)
   {
      int newCount = afterCount - beforeCount;
      bool anyHighlight = false;
      string firstLabel = "";
      ENUM_ZI_TYPE firstType = ZI_BUY;
      for(int idx = beforeCount; idx < afterCount; idx++)
      {
         ZI_Zone z;
         if(!g_engine.GetZone(idx, z)) continue;
         if(z.strength >= g_min_confluence) anyHighlight = true;
         if(firstLabel == "") { firstLabel = z.label; firstType = z.type; }
      }
      string msg = StringFormat("%s SMC_ZonesInd: %d new zone(s) formed (last: %s %s)",
                                 _Symbol, newCount, firstLabel, (firstType == ZI_BUY ? "BUY" : "SELL"));
      ZI_Alert(msg, g_alert_push, g_alert_sound, g_lastAlertNewZone, time[rates_total - 2]);

      if(anyHighlight)
      {
         string msg2 = StringFormat("%s SMC_ZonesInd: A+ confluence zone (strength>=%d)", _Symbol, g_min_confluence);
         ZI_Alert(msg2, g_alert_push, g_alert_sound, g_lastAlertConfluence, time[rates_total - 2]);
      }
   }

   SyncZoneObjects();
   CheckTouchAlerts();

   return rates_total;
}
