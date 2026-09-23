//+------------------------------------------------------------------+
//|                                                VWAP_ZonesInd.mq5 |
//| Session VWAP (daily reset) with volume-weighted deviation bands   |
//| (+-1sigma/+-2sigma) and bidirectional volume-exhaustion zone      |
//| detection at band touches. Detection-only indicator - no order    |
//| execution.                                                         |
//|                                                                    |
//| Basado en mql5.com/es/articles/10329 (Daniel Jose) - session VWAP |
//|   core, adapted for the suite's incremental engine-state           |
//|   convention (see VWAP_ZonesEngine.mqh header for details).        |
//| Basado en mql5.com/es/articles/130 (Sergey Greecie) - center       |
//|   +/- k*StdDev band-construction technique, adapted to a true      |
//|   volume-weighted variance around VWAP (see VWAP_ZonesEngine.mqh   |
//|   header for the derivation).                                      |
//| Volume-exhaustion detection has no corpus precedent - original     |
//|   logic, see VWAP_ZonesEngine.mqh header.                          |
//| Panel pattern copied from ZoneIndicators\MQL5\Include\CRT_ZonesInd |
//| \CRT_ZonesPanel.mqh (itself from SMC_ZonesPanel.mqh).              |
//+------------------------------------------------------------------+
#property copyright   "Zone Indicators Suite"
#property link        ""
#property version     "1.00"
#property indicator_chart_window
#property indicator_buffers 5
#property indicator_plots   5

#property indicator_label1  "VWAP"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrYellow
#property indicator_style1  STYLE_SOLID
#property indicator_width1  2

#property indicator_label2  "VWAP +1sig"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrDodgerBlue
#property indicator_style2  STYLE_DOT
#property indicator_width2  1

#property indicator_label3  "VWAP -1sig"
#property indicator_type3   DRAW_LINE
#property indicator_color3  clrDodgerBlue
#property indicator_style3  STYLE_DOT
#property indicator_width3  1

#property indicator_label4  "VWAP +2sig"
#property indicator_type4   DRAW_LINE
#property indicator_color4  clrOrangeRed
#property indicator_style4  STYLE_DOT
#property indicator_width4  1

#property indicator_label5  "VWAP -2sig"
#property indicator_type5   DRAW_LINE
#property indicator_color5  clrOrangeRed
#property indicator_style5  STYLE_DOT
#property indicator_width5  1

#include <ZoneIndicators\ZI_Common.mqh>
#include <VWAP_ZonesInd\VWAP_ZonesEngine.mqh>
#include <VWAP_ZonesInd\VWAP_ZonesPanel.mqh>

//+------------------------------------------------------------------+
//| Inputs                                                            |
//+------------------------------------------------------------------+
input string Section_VWAP          = "==== VWAP Detection ====";  // VWAP Detection
input double InpBand1Mult          = 1.0;  // Deviation Band 1 multiplier (sigma)
input double InpBand2Mult          = 2.0;  // Deviation Band 2 multiplier (sigma)
input int    InpTouchBand          = 1;    // Touch Band for Zone Trigger (1 or 2 sigma)
input int    InpExhaustionBars     = 5;    // Volume-Exhaustion Window (N bars, declining-volume chain incl. touch bar)
input bool   InpUseRealVolume      = false; // Use VOLUME_REAL when available (else VOLUME_TICK; per-bar fallback if real=0)

input string Section_Alerts    = "==== Alerts ====";  // Alerts
input bool   InpAlertPush      = true;    // Push Notification on New Zone / A+
input bool   InpAlertSound     = true;    // Sound Alert on New Zone / A+
input bool   InpAlertOnTouch   = false;   // Also Alert When an Existing Zone is Touched

input string Section_Panel     = "==== Control Panel ====";  // Control Panel
input bool   InpShowPanel      = true;    // Show Control Panel
input int    InpPanelCorner    = 0;       // Panel Anchor (0=UL,1=UR,2=LL,3=LR)
input int    InpPanelX         = 20;      // Panel X Offset (pixels)
input int    InpPanelY         = 20;      // Panel Y Offset (pixels)
input int    InpMinZoneStrength = 2;      // Min Strength for A+ Highlight (1-3)

input string Section_Layers    = "==== Layers (default) ====";  // Layers
input bool   InpShowVwapLine   = true;    // Show VWAP Line
input bool   InpShowBands      = true;    // Show Deviation Bands
input bool   InpShowZones      = true;    // Show Zones

input string Section_Colors    = "==== Colors ====";  // Colors
input color  InpColorBuy           = C'20,150,130';  // Buy Zone Color
input color  InpColorSell          = C'180,40,40';   // Sell Zone Color
input color  InpColorHighlightBuy  = clrLime;         // Buy Zone Color (A+ Strength)
input color  InpColorHighlightSell = clrRed;          // Sell Zone Color (A+ Strength)

//+------------------------------------------------------------------+
//| Buffers                                                            |
//+------------------------------------------------------------------+
double BufferVWAP[];
double BufferUpper1[];
double BufferLower1[];
double BufferUpper2[];
double BufferLower2[];

//+------------------------------------------------------------------+
//| Globals                                                            |
//+------------------------------------------------------------------+
CVWAPZonesEngine g_engine;
CVWAPZonesPanel  ExtPanel;

// g_min_zone_strength is declared in VWAP_ZonesPanel.mqh (panel-owned, direct-set
// by its live spin edit - see that file's header comment for why this one control
// doesn't need the touch-band/exhaustion-bars request/apply indirection).

datetime g_lastAlertNewZone    = 0;
datetime g_lastAlertConfluence = 0;
datetime g_lastAlertTouch      = 0;

//+------------------------------------------------------------------+
string ZoneObjName(const ZI_Zone &z)
{
   return StringFormat("ZI_VWAP_ZONE_%s_%I64d", (z.type == ZI_BUY ? "BUY" : "SELL"), (long)z.bar_time);
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

   bool highlight = (z.strength >= g_min_zone_strength);
   color clr = ZoneColor(z.type, highlight);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, highlight ? 2 : 1);

   string txt = StringFormat("VWAP %s%s (%d)", (z.type == ZI_BUY ? "BUY" : "SELL"),
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

//+------------------------------------------------------------------+
//| Reconciles chart objects with the engine's current zone list -    |
//| same shape as CRT_ZonesInd.mq5's SyncZoneObjects(), including     |
//| draining the pending-deletion queue for cap-evicted zones so they |
//| don't orphan their OBJ_RECTANGLE/OBJ_TEXT on the chart forever.   |
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
         string msg = StringFormat("%s VWAP %s zone touched: [%.5f-%.5f] strength=%d",
                                    _Symbol, (z.type == ZI_BUY ? "BUY" : "SELL"),
                                    z.price_lo, z.price_hi, z.strength);
         ZI_Alert(msg, g_alert_push, g_alert_sound, g_lastAlertTouch, iTime(_Symbol, _Period, 0));
      }
   }
}

//+------------------------------------------------------------------+
//| Applies panel-requested live parameter changes (touch band /       |
//| exhaustion window) to the engine. Same request/apply flow as       |
//| CRT_ZonesInd.mq5's ApplyPendingRangeModeChange() - the panel        |
//| cannot reach the engine object directly.                           |
//+------------------------------------------------------------------+
void ApplyPendingPanelRequests(void)
{
   if(g_touch_band_request >= 0)
   {
      if(g_touch_band_request != g_engine.TouchBand())
         g_engine.SetTouchBand(g_touch_band_request);
      g_touch_band_request = -1;
   }
   if(g_exhaustion_bars_request >= 0)
   {
      if(g_exhaustion_bars_request != g_engine.ExhaustionBars())
         g_engine.SetExhaustionBars(g_exhaustion_bars_request);
      g_exhaustion_bars_request = -1;
   }
}

//+------------------------------------------------------------------+
int OnInit()
{
   SetIndexBuffer(0, BufferVWAP,   INDICATOR_DATA);
   SetIndexBuffer(1, BufferUpper1, INDICATOR_DATA);
   SetIndexBuffer(2, BufferLower1, INDICATOR_DATA);
   SetIndexBuffer(3, BufferUpper2, INDICATOR_DATA);
   SetIndexBuffer(4, BufferLower2, INDICATOR_DATA);
   ArraySetAsSeries(BufferVWAP,   false);
   ArraySetAsSeries(BufferUpper1, false);
   ArraySetAsSeries(BufferLower1, false);
   ArraySetAsSeries(BufferUpper2, false);
   ArraySetAsSeries(BufferLower2, false);
   for(int p = 0; p < 5; p++)
      PlotIndexSetDouble(p, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetInteger(0, PLOT_DRAW_TYPE, InpShowVwapLine ? DRAW_LINE : DRAW_NONE);
   for(int p = 1; p <= 4; p++)
      PlotIndexSetInteger(p, PLOT_DRAW_TYPE, InpShowBands ? DRAW_LINE : DRAW_NONE);

   g_show_vwap_line = InpShowVwapLine;
   g_show_bands     = InpShowBands;
   g_show_zones     = InpShowZones;
   g_min_zone_strength = (InpMinZoneStrength >= 1 && InpMinZoneStrength <= 3) ? InpMinZoneStrength : 2;
   g_alert_push  = InpAlertPush;
   g_alert_sound = InpAlertSound;
   g_panel_force_redraw = false;
   g_touch_band_request = -1;
   g_exhaustion_bars_request = -1;

   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(point <= 0.0) point = _Point;

   int touchBand = (InpTouchBand == 2) ? 2 : 1;
   int exhaustionBars = (InpExhaustionBars >= 2) ? InpExhaustionBars : 5;

   g_engine.Configure(InpBand1Mult, InpBand2Mult, touchBand, exhaustionBars, InpUseRealVolume, point);

   g_lastAlertNewZone    = 0;
   g_lastAlertConfluence = 0;
   g_lastAlertTouch      = 0;

   ObjectsDeleteAll(0, "ZI_VWAP_");

   if(InpShowPanel)
   {
      ChartSetInteger(0, CHART_EVENT_MOUSE_MOVE, true);
      if(!ExtPanel.CreateAt(0, 0, InpPanelCorner, InpPanelX, InpPanelY, touchBand, exhaustionBars))
      {
         Print("VWAP_ZonesInd: failed to create control panel");
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
   ObjectsDeleteAll(0, "ZI_VWAP_");
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

   ApplyPendingPanelRequests();

   bool isHistoryReplay = (prev_calculated == 0);
   int limit = isHistoryReplay ? 0 : prev_calculated - 1;
   if(limit < 0) limit = 0;

   int beforeCount = g_engine.ZonesTotal();
   for(int i = limit; i < rates_total - 1; i++)
   {
      g_engine.ProcessClosedBar(i, time, high, low, close, tick_volume, volume);
      bool ready = g_engine.VWAPReady();
      BufferVWAP[i]   = ready ? g_engine.VWAP()       : EMPTY_VALUE;
      BufferUpper1[i] = ready ? g_engine.Band1Upper()  : EMPTY_VALUE;
      BufferLower1[i] = ready ? g_engine.Band1Lower()  : EMPTY_VALUE;
      BufferUpper2[i] = ready ? g_engine.Band2Upper()  : EMPTY_VALUE;
      BufferLower2[i] = ready ? g_engine.Band2Lower()  : EMPTY_VALUE;
   }
   int afterCount = g_engine.ZonesTotal();

   // Forming (unclosed) last bar: display continuity only, not a new detection
   // decision - carries the last closed bar's values forward rather than
   // recomputing against a still-moving bar (project rule: detection/values
   // never evaluated on the forming candle).
   int lastIdx = rates_total - 1;
   if(lastIdx > 0)
   {
      BufferVWAP[lastIdx]   = BufferVWAP[lastIdx - 1];
      BufferUpper1[lastIdx] = BufferUpper1[lastIdx - 1];
      BufferLower1[lastIdx] = BufferLower1[lastIdx - 1];
      BufferUpper2[lastIdx] = BufferUpper2[lastIdx - 1];
      BufferLower2[lastIdx] = BufferLower2[lastIdx - 1];
   }

   if(!isHistoryReplay && afterCount > beforeCount)
   {
      int newCount = afterCount - beforeCount;
      bool anyHighlight = false;
      ENUM_ZI_TYPE firstType = ZI_BUY;
      for(int idx = beforeCount; idx < afterCount; idx++)
      {
         ZI_Zone z;
         if(!g_engine.GetZone(idx, z)) continue;
         if(z.strength >= g_min_zone_strength) anyHighlight = true;
         if(idx == beforeCount) firstType = z.type;
      }
      string msg = StringFormat("%s VWAP_ZonesInd: %d new zone(s) formed (last: %s)",
                                 _Symbol, newCount, (firstType == ZI_BUY ? "BUY" : "SELL"));
      ZI_Alert(msg, g_alert_push, g_alert_sound, g_lastAlertNewZone, time[rates_total - 2]);

      if(anyHighlight)
      {
         string msg2 = StringFormat("%s VWAP_ZonesInd: A+ strength zone (>=%d)", _Symbol, g_min_zone_strength);
         ZI_Alert(msg2, g_alert_push, g_alert_sound, g_lastAlertConfluence, time[rates_total - 2]);
      }
   }

   SyncZoneObjects();
   CheckTouchAlerts();

   return rates_total;
}
