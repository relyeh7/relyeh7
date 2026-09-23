//+------------------------------------------------------------------+
//|                                                 CRT_ZonesInd.mq5 |
//| Bidirectional Candle Range Theory zones: a reference range        |
//| (previous Daily/4H/Session period's high/low) is frozen, then the |
//| next period is watched for a manipulation sweep past that range   |
//| and a distribution/reentry close back inside it. Detection-only   |
//| indicator - no order execution.                                   |
//|                                                                    |
//| Basado en mql5.com/es/articles/18911 (Christian Benjamin) -       |
//|   CRangePattern's true-range/ATR formula, adapted for the sweep   |
//|   strength filter (see CRT_ZonesEngine.mqh header for details).   |
//| Panel pattern copied from ZoneIndicators\MQL5\Include\SMC_ZonesInd|
//| \SMC_ZonesPanel.mqh (itself from H:\Dev-Drive\SMC\SMC_Indicator.  |
//| mq5).                                                              |
//+------------------------------------------------------------------+
#property copyright   "Zone Indicators Suite"
#property link        ""
#property version     "1.00"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

#include <ZoneIndicators\ZI_Common.mqh>
#include <CRT_ZonesInd\CRT_ZonesEngine.mqh>
#include <CRT_ZonesInd\CRT_ZonesPanel.mqh>

//+------------------------------------------------------------------+
//| Inputs                                                            |
//+------------------------------------------------------------------+
input string Section_CRT           = "==== CRT Detection ====";  // CRT Detection
input ENUM_CRT_RANGE_MODE InpRangeMode = CRT_RANGE_DAILY;  // Reference Range (Daily/4H/Session)
input int    InpSessionAsiaHour    = 0;    // Session mode: Asia start hour (broker time, 0-23)
input int    InpSessionLondonHour  = 8;    // Session mode: London start hour (broker time, 0-23)
input int    InpSessionNYHour      = 13;   // Session mode: New York start hour (broker time, 0-23)
input int    InpATRPeriod          = 14;   // ATR period (strength filter)
input bool   InpUseATRFilter       = true; // Use ATR multiple for sweep strength filter (else fixed points)
input double InpMinSweepPoints     = 50.0; // Min sweep distance beyond range (points) - used if ATR filter off
input double InpMinSweepATRMult    = 0.25; // Min sweep distance beyond range (x ATR) - used if ATR filter on
input int    InpMaxReentryBars     = 10;   // Max bars a sweep may wait for reentry before expiring

input string Section_Alerts    = "==== Alerts ====";  // Alerts
input bool   InpAlertPush      = true;    // Push Notification on New Zone / A+
input bool   InpAlertSound     = true;    // Sound Alert on New Zone / A+
input bool   InpAlertOnTouch   = false;   // Also Alert When an Existing Zone is Touched

input string Section_Panel     = "==== Control Panel ====";  // Control Panel
input bool   InpShowPanel      = true;    // Show Control Panel
input int    InpPanelCorner    = 0;       // Panel Anchor (0=UL,1=UR,2=LL,3=LR)
input int    InpPanelX         = 20;      // Panel X Offset (pixels)
input int    InpPanelY         = 20;      // Panel Y Offset (pixels)
input int    InpMinSweepStrength = 2;     // Min Strength for A+ Highlight (1-3)

input string Section_Layers    = "==== Zone Layers (default) ====";  // Zone Layers
input bool   InpShowZones      = true;    // Show CRT Zones
input bool   InpShowRange      = true;    // Show Reference Range

input string Section_Colors    = "==== Colors ====";  // Colors
input color  InpColorBuy           = C'20,150,130';  // Buy Zone Color
input color  InpColorSell          = C'180,40,40';   // Sell Zone Color
input color  InpColorHighlightBuy  = clrLime;         // Buy Zone Color (A+ Strength)
input color  InpColorHighlightSell = clrRed;          // Sell Zone Color (A+ Strength)
input color  InpColorRange         = clrSilver;       // Reference Range Box Color

//+------------------------------------------------------------------+
//| Globals                                                           |
//+------------------------------------------------------------------+
CCRTZonesEngine g_engine;
CCRTZonesPanel  ExtPanel;

datetime g_lastAlertNewZone    = 0;
datetime g_lastAlertConfluence = 0;
datetime g_lastAlertTouch      = 0;

//+------------------------------------------------------------------+
string ZoneObjName(const ZI_Zone &z)
{
   return StringFormat("ZI_CRT_ZONE_%s_%I64d", (z.type == ZI_BUY ? "BUY" : "SELL"), (long)z.bar_time);
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

   bool highlight = (z.strength >= g_min_sweep_strength);
   color clr = ZoneColor(z.type, highlight);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, highlight ? 2 : 1);

   string txt = StringFormat("CRT %s%s (%d)", (z.type == ZI_BUY ? "BUY" : "SELL"),
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

void DrawRangeBox(void)
{
   string name  = "ZI_CRT_RANGE_Box";
   string tname = "ZI_CRT_RANGE_Box_txt";
   if(!g_show_range || !g_engine.HasRange())
   {
      ObjectDelete(0, name);
      ObjectDelete(0, tname);
      return;
   }

   double hi = g_engine.RangeHi();
   double lo = g_engine.RangeLo();
   datetime t2 = TimeCurrent() + PeriodSeconds() * 5;

   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_RECTANGLE, 0, TimeCurrent(), hi, t2, lo);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_FILL, false);
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DOT);
   }
   else
   {
      ObjectMove(0, name, 1, t2, lo);
      ObjectSetDouble(0, name, OBJPROP_PRICE, 0, hi); // corner 0 price = hi
   }
   ObjectSetInteger(0, name, OBJPROP_COLOR, InpColorRange);

   string txt = StringFormat("CRT RANGE (%s)", EnumToString(g_engine.RangeMode()));
   if(ObjectFind(0, tname) < 0)
   {
      ObjectCreate(0, tname, OBJ_TEXT, 0, TimeCurrent(), hi);
      ObjectSetInteger(0, tname, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, tname, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, tname, OBJPROP_FONTSIZE, 7);
      ObjectSetInteger(0, tname, OBJPROP_COLOR, InpColorRange);
   }
   else
      ObjectMove(0, tname, 0, TimeCurrent(), hi);
   ObjectSetString(0, tname, OBJPROP_TEXT, txt);
}

//+------------------------------------------------------------------+
//| Reconciles chart objects with the engine's current zone list:     |
//| draws/updates active zones whose layer is enabled, deletes        |
//| objects for mitigated or hidden zones, then compacts the array.   |
//| Also drains the engine's pending-deletion queue: zones the        |
//| CRT_MAX_ZONES cap evicted (mitigated or not) still need their     |
//| chart objects removed, or they orphan on the chart forever since  |
//| the main zone loop below only sees what's still in the engine.    |
//+------------------------------------------------------------------+
void SyncZoneObjects(void)
{
   int pending = g_engine.PendingDeletionsTotal();
   for(int idx = 0; idx < pending; idx++)
   {
      ZI_Zone z;
      if(g_engine.GetPendingDeletion(idx, z))
      {
         string pendingName = ZoneObjName(z);
         DeleteZoneObj(pendingName);
      }
   }
   g_engine.ClearPendingDeletions();

   int n = g_engine.ZonesTotal();
   for(int idx = 0; idx < n; idx++)
   {
      ZI_Zone z;
      if(!g_engine.GetZone(idx, z)) continue;
      string name = ZoneObjName(z);
      if(g_engine.IsMitigated(idx) || !g_show_zones)
         DeleteZoneObj(name);
      else
         DrawOrUpdateZone(name, z);
   }
   g_engine.RemoveMitigated();
   DrawRangeBox();
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
         string msg = StringFormat("%s CRT %s zone touched: [%.5f-%.5f] strength=%d",
                                    _Symbol, (z.type == ZI_BUY ? "BUY" : "SELL"),
                                    z.price_lo, z.price_hi, z.strength);
         ZI_Alert(msg, g_alert_push, g_alert_sound, g_lastAlertTouch, iTime(_Symbol, _Period, 0));
      }
   }
}

//+------------------------------------------------------------------+
//| Applies a range-mode change requested from the panel's spin edit. |
//| The panel can only write to its own g_* globals (it never touches |
//| g_engine directly), so the main program applies the request here. |
//+------------------------------------------------------------------+
void ApplyPendingRangeModeChange(void)
{
   if(g_range_mode_request < 0) return;
   if(g_range_mode_request != (int)g_engine.RangeMode())
      g_engine.ResetRangeMode((ENUM_CRT_RANGE_MODE)g_range_mode_request);
   g_range_mode_request = -1;
}

//+------------------------------------------------------------------+
int OnInit()
{
   g_show_zones = InpShowZones;
   g_show_range = InpShowRange;
   g_min_sweep_strength = (InpMinSweepStrength >= 1 && InpMinSweepStrength <= 3) ? InpMinSweepStrength : 2;
   g_alert_push  = InpAlertPush;
   g_alert_sound = InpAlertSound;
   g_panel_force_redraw = false;
   g_range_mode_request = -1;

   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(point <= 0.0) point = _Point;

   int sessionHours[3];
   sessionHours[0] = InpSessionAsiaHour;
   sessionHours[1] = InpSessionLondonHour;
   sessionHours[2] = InpSessionNYHour;

   g_engine.Configure(InpRangeMode, sessionHours, InpATRPeriod, InpUseATRFilter,
                       InpMinSweepPoints, InpMinSweepATRMult, InpMaxReentryBars, point);

   g_lastAlertNewZone    = 0;
   g_lastAlertConfluence = 0;
   g_lastAlertTouch      = 0;

   ObjectsDeleteAll(0, "ZI_CRT_");

   if(InpShowPanel)
   {
      ChartSetInteger(0, CHART_EVENT_MOUSE_MOVE, true);
      if(!ExtPanel.CreateAt(0, 0, InpPanelCorner, InpPanelX, InpPanelY, InpRangeMode))
      {
         Print("CRT_ZonesInd: failed to create control panel");
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
   ObjectsDeleteAll(0, "ZI_CRT_");
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
   if(rates_total < 2) return 0;

   ApplyPendingRangeModeChange();

   bool isHistoryReplay = (prev_calculated == 0);
   int limit = isHistoryReplay ? 0 : prev_calculated - 1;
   if(limit < 0) limit = 0;

   int beforeCount = g_engine.ZonesTotal();
   for(int i = limit; i < rates_total - 1; i++)
      g_engine.ProcessClosedBar(i, time, open, high, low, close);
   int afterCount = g_engine.ZonesTotal();

   if(!isHistoryReplay && afterCount > beforeCount)
   {
      int newCount = afterCount - beforeCount;
      bool anyHighlight = false;
      ENUM_ZI_TYPE firstType = ZI_BUY;
      for(int idx = beforeCount; idx < afterCount; idx++)
      {
         ZI_Zone z;
         if(!g_engine.GetZone(idx, z)) continue;
         if(z.strength >= g_min_sweep_strength) anyHighlight = true;
         if(idx == beforeCount) firstType = z.type;
      }
      string msg = StringFormat("%s CRT_ZonesInd: %d new zone(s) formed (last: %s)",
                                 _Symbol, newCount, (firstType == ZI_BUY ? "BUY" : "SELL"));
      ZI_Alert(msg, g_alert_push, g_alert_sound, g_lastAlertNewZone, time[rates_total - 2]);

      if(anyHighlight)
      {
         string msg2 = StringFormat("%s CRT_ZonesInd: A+ strength zone (>=%d)", _Symbol, g_min_sweep_strength);
         ZI_Alert(msg2, g_alert_push, g_alert_sound, g_lastAlertConfluence, time[rates_total - 2]);
      }
   }

   SyncZoneObjects();
   CheckTouchAlerts();

   return rates_total;
}
