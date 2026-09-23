//+------------------------------------------------------------------+
//| VWAP_ZonesPanel.mqh - CAppDialog control panel for VWAP_ZonesInd  |
//| Pattern copied from ZoneIndicators\MQL5\Include\CRT_ZonesInd\     |
//| CRT_ZonesPanel.mqh (itself from SMC_ZonesPanel.mqh / SMC_Indicator|
//| .mq5's CSMCMtfPanel): corner anchoring, dark-background checkboxes,|
//| timer-driven refresh, caption-X survival. UI only - no detection. |
//+------------------------------------------------------------------+
#ifndef VWAP_ZONES_PANEL_MQH
#define VWAP_ZONES_PANEL_MQH

#property strict

#include <Controls\Dialog.mqh>
#include <Controls\Panel.mqh>
#include <Controls\Label.mqh>
#include <Controls\Button.mqh>
#include <Controls\CheckBox.mqh>
#include <Controls\SpinEdit.mqh>
#include <VWAP_ZonesInd\VWAP_ZonesEngine.mqh>

//--- Runtime-mutable flags the panel owns. Drawing/alert code reads ONLY these,
//--- never the Inp* inputs directly (seeded once from Inp* in OnInit).
bool g_show_vwap_line = true;
bool g_show_bands     = true;
bool g_show_zones     = true;
bool g_alert_push     = true;
bool g_alert_sound    = true;
bool g_panel_force_redraw = false; // set true when a layer is re-enabled

//--- Set by the panel's live spin edits; the main .mq5 reads these once per
//--- tick and calls the matching g_engine setter when they differ from the
//--- engine's own value - the panel cannot reach the engine object directly.
int  g_touch_band_request      = -1; // -1 = no pending change
int  g_exhaustion_bars_request = -1; // -1 = no pending change

#define VWP_CLR_BG      C'16,18,24'
#define VWP_CLR_HDR     C'25,45,80'
#define VWP_CLR_LBL     clrWhite
#define VWP_DLG_W       260
#define VWP_IND         10
#define VWP_HDR_H       20
#define VWP_ROW_H       18
#define VWP_CHK_H       20
#define VWP_GAP         6
#define VWP_CHK_W       120

//+------------------------------------------------------------------+
//| Resolve a corner anchor into CAppDialog's absolute-pixel space    |
//+------------------------------------------------------------------+
void VWP_ResolveOrigin(const int corner, const int off_x, const int off_y,
                        const int dlg_w, const int dlg_h, int &out_x, int &out_y)
{
   out_x = off_x;
   out_y = off_y;
   int chart_w = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS, 0);
   int chart_h = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS, 0);
   if(chart_w <= 0 || chart_h <= 0) return; // not measurable yet: use raw offsets
   if(corner == 1 || corner == 3) out_x = chart_w - dlg_w - off_x;
   if(corner == 2 || corner == 3) out_y = chart_h - dlg_h - off_y;
   if(out_x < 0) out_x = 0;
   if(out_y < 0) out_y = 0;
}

//+------------------------------------------------------------------+
//| CVWAPDarkCheckBox - CCheckBox that survives a dark panel background|
//+------------------------------------------------------------------+
class CVWAPDarkCheckBox : public CCheckBox
{
public:
   bool Recolor(const color bg, const color text)
   {
      string obj = m_name + "Label";
      if(ObjectFind(m_chart_id, obj) < 0) return false;
      ObjectSetInteger(m_chart_id, obj, OBJPROP_BGCOLOR, bg);
      ObjectSetInteger(m_chart_id, obj, OBJPROP_BORDER_COLOR, bg);
      return Color(text);
   }
};

//+------------------------------------------------------------------+
//| CVWAPZonesPanel                                                   |
//+------------------------------------------------------------------+
class CVWAPZonesPanel : public CAppDialog
{
private:
   CPanel            m_bg;
   CPanel            m_bar_layers;
   CLabel            m_lbl_layers;
   CVWAPDarkCheckBox m_chk_vwap;
   CVWAPDarkCheckBox m_chk_bands;
   CVWAPDarkCheckBox m_chk_zones;
   CPanel            m_bar_touch;
   CLabel            m_lbl_touch;
   CLabel            m_lbl_touch_val;
   CSpinEdit         m_spin_touch;
   CPanel            m_bar_exh;
   CLabel            m_lbl_exh;
   CSpinEdit         m_spin_exh;
   CPanel            m_bar_alerts;
   CLabel            m_lbl_alerts;
   CVWAPDarkCheckBox m_chk_push;
   CVWAPDarkCheckBox m_chk_sound;

   int               m_client_h;
   int               m_y_layers, m_y_chk1, m_y_chk1b, m_y_touch, m_y_exh, m_y_alerts, m_y_chk2;

public:
                     CVWAPZonesPanel(void) : m_client_h(0) {}
                    ~CVWAPZonesPanel(void) {}

   bool              CreateAt(const long chart, const int subwin, const int corner,
                               const int off_x, const int off_y, const int initialTouchBand,
                               const int initialExhaustionBars);
   virtual bool      OnEvent(const int id, const long &lparam, const double &dparam, const string &sparam);
   void              Refresh(void);

protected:
   void              Layout(void);
   bool              CreateControls(const int initialTouchBand, const int initialExhaustionBars);
   bool              MakeLabel(CLabel &l, const string id, const int x, const int y, const int w,
                                const string text, const color clr, const int size = 8,
                                const string font = "Segoe UI");
   bool              MakeBar(CPanel &p, const string id, const int x, const int y, const int w,
                              const int h, const color clr);
   bool              MakeCheck(CVWAPDarkCheckBox &c, const string id, const int x, const int y,
                                const int w, const string text, const bool checked);
   void              LayerToggled(const string layer_prefix, const bool now_on);
   void              SetPlotVisible(const int plot_index, const bool visible);

   void              OnChangeVwapLine(void);
   void              OnChangeBands(void);
   void              OnChangeZones(void);
   void              OnChangeTouch(void);
   void              OnChangeExh(void);
   void              OnChangePush(void);
   void              OnChangeSound(void);
};

//+------------------------------------------------------------------+
void CVWAPZonesPanel::Layout(void)
{
   int y = VWP_IND;
   m_y_layers = y; y += VWP_HDR_H + VWP_GAP;
   m_y_chk1   = y; y += VWP_CHK_H + 2;
   m_y_chk1b  = y; y += VWP_CHK_H + VWP_GAP;
   m_y_touch  = y; y += VWP_HDR_H + VWP_GAP;
   m_y_exh    = y; y += VWP_HDR_H + VWP_GAP;
   m_y_alerts = y; y += VWP_HDR_H + VWP_GAP;
   m_y_chk2   = y; y += VWP_CHK_H;
   m_client_h = y + VWP_IND;
}

//+------------------------------------------------------------------+
bool CVWAPZonesPanel::MakeLabel(CLabel &l, const string id, const int x, const int y, const int w,
                                 const string text, const color clr, const int size, const string font)
{
   if(!l.Create(m_chart_id, m_name + id, m_subwin, x, y, x + w, y + VWP_ROW_H)) return false;
   if(!Add(l)) return false;
   l.Font(font);
   l.FontSize(size);
   l.Color(clr);
   l.Text(text);
   return true;
}

bool CVWAPZonesPanel::MakeBar(CPanel &p, const string id, const int x, const int y, const int w,
                               const int h, const color clr)
{
   if(!p.Create(m_chart_id, m_name + id, m_subwin, x, y, x + w, y + h)) return false;
   if(!Add(p)) return false;
   p.ColorBackground(clr);
   p.ColorBorder(clr);
   p.BorderType(BORDER_FLAT);
   return true;
}

bool CVWAPZonesPanel::MakeCheck(CVWAPDarkCheckBox &c, const string id, const int x, const int y,
                                 const int w, const string text, const bool checked)
{
   if(!c.Create(m_chart_id, m_name + id, m_subwin, x, y, x + w, y + VWP_CHK_H)) return false;
   if(!Add(c)) return false;
   c.Text(text);
   c.Checked(checked);
   c.Recolor(VWP_CLR_BG, clrWhite); // must run after Create: the caption object doesn't exist before it
   return true;
}

//+------------------------------------------------------------------+
bool CVWAPZonesPanel::CreateAt(const long chart, const int subwin, const int corner,
                                const int off_x, const int off_y, const int initialTouchBand,
                                const int initialExhaustionBars)
{
   Layout();
   int dlg_h = m_client_h + 28;
   int x, y;
   VWP_ResolveOrigin(corner, off_x, off_y, VWP_DLG_W, dlg_h, x, y);

   if(!CAppDialog::Create(chart, "VWAPZones", subwin, x, y, x + VWP_DLG_W, y + dlg_h))
      return false;

   Caption("VWAP ZONES");

   if(!CreateControls(initialTouchBand, initialExhaustionBars)) return false;

   Refresh();
   return true;
}

bool CVWAPZonesPanel::CreateControls(const int initialTouchBand, const int initialExhaustionBars)
{
   int full_w = VWP_DLG_W - 12 - 2 * VWP_IND;

   if(!MakeBar(m_bg, "BG", 0, 0, VWP_DLG_W - 12, m_client_h, VWP_CLR_BG)) return false;

   //--- Layer toggles
   if(!MakeBar(m_bar_layers, "BarLay", VWP_IND, m_y_layers, full_w, VWP_HDR_H, VWP_CLR_HDR)) return false;
   if(!MakeLabel(m_lbl_layers, "LblLay", VWP_IND + 6, m_y_layers, full_w - 6, "LAYERS", clrWhite, 7, "Segoe UI Semibold"))
      return false;

   int col2_x = VWP_IND + VWP_CHK_W + 10;
   if(!MakeCheck(m_chk_vwap,  "ChkVwap",  VWP_IND, m_y_chk1, VWP_CHK_W, "VWAP Line",       g_show_vwap_line)) return false;
   if(!MakeCheck(m_chk_bands, "ChkBands", col2_x,  m_y_chk1, VWP_CHK_W, "Deviation Bands", g_show_bands))     return false;
   // Zones checkbox on its own row below the first pair (three toggles, two columns).
   if(!MakeCheck(m_chk_zones, "ChkZones", VWP_IND, m_y_chk1b, VWP_CHK_W, "Zones", g_show_zones)) return false;

   //--- Touch band selector (which sigma band counts as a zone-triggering touch)
   if(!MakeBar(m_bar_touch, "BarTouch", VWP_IND, m_y_touch, full_w, VWP_HDR_H, VWP_CLR_HDR)) return false;
   if(!MakeLabel(m_lbl_touch, "LblTouch", VWP_IND + 6, m_y_touch, 90, "TOUCH BAND", clrWhite, 7, "Segoe UI Semibold"))
      return false;
   if(!m_spin_touch.Create(m_chart_id, m_name + "SpinTouch", m_subwin,
                            VWP_IND + full_w - 40, m_y_touch, VWP_IND + full_w - 6, m_y_touch + VWP_HDR_H))
      return false;
   if(!Add(m_spin_touch)) return false;
   m_spin_touch.MinValue(1);
   m_spin_touch.MaxValue(2);
   m_spin_touch.Value(initialTouchBand);
   if(!MakeLabel(m_lbl_touch_val, "LblTouchVal", VWP_IND + 90, m_y_touch, full_w - 90 - 42,
                 (initialTouchBand == 2 ? "2-sigma" : "1-sigma"), clrSilver, 7))
      return false;

   //--- Volume-exhaustion window size (N bars)
   if(!MakeBar(m_bar_exh, "BarExh", VWP_IND, m_y_exh, full_w, VWP_HDR_H, VWP_CLR_HDR)) return false;
   if(!MakeLabel(m_lbl_exh, "LblExh", VWP_IND + 6, m_y_exh, 170, "EXHAUSTION BARS (N)", clrWhite, 7, "Segoe UI Semibold"))
      return false;
   if(!m_spin_exh.Create(m_chart_id, m_name + "SpinExh", m_subwin,
                          VWP_IND + full_w - 40, m_y_exh, VWP_IND + full_w - 6, m_y_exh + VWP_HDR_H))
      return false;
   if(!Add(m_spin_exh)) return false;
   m_spin_exh.MinValue(2);
   m_spin_exh.MaxValue(30);
   m_spin_exh.Value(initialExhaustionBars);

   //--- Alerts
   if(!MakeBar(m_bar_alerts, "BarAl", VWP_IND, m_y_alerts, full_w, VWP_HDR_H, VWP_CLR_HDR)) return false;
   if(!MakeLabel(m_lbl_alerts, "LblAl", VWP_IND + 6, m_y_alerts, full_w - 6, "ALERTS", clrWhite, 7, "Segoe UI Semibold"))
      return false;
   if(!MakeCheck(m_chk_push,  "ChkPush",  VWP_IND, m_y_chk2, VWP_CHK_W, "Push notification", g_alert_push))  return false;
   if(!MakeCheck(m_chk_sound, "ChkSound", col2_x,  m_y_chk2, VWP_CHK_W, "Sound alert",        g_alert_sound)) return false;

   return true;
}

//+------------------------------------------------------------------+
void CVWAPZonesPanel::Refresh(void)
{
   //--- Panel may have been closed with the caption X; the program (and its
   //--- timer) keeps running, so guard against writing to dead controls.
   if(ObjectFind(m_chart_id, m_chk_vwap.Name()) < 0) return;
   ChartRedraw(m_chart_id);
}

//+------------------------------------------------------------------+
void CVWAPZonesPanel::LayerToggled(const string layer_prefix, const bool now_on)
{
   if(!now_on && layer_prefix != "")
      ObjectsDeleteAll(0, layer_prefix);
   else
      g_panel_force_redraw = true; // re-enabled: next OnCalculate tick repaints it from live zones
   ChartRedraw(m_chart_id);
}

//+------------------------------------------------------------------+
//| Shows/hides an indicator plot line (VWAP / band buffers) - these   |
//| are PLOT_DRAW_TYPE-driven buffers, not chart objects, so they      |
//| can't go through LayerToggled()'s ObjectsDeleteAll path. Callable  |
//| directly from the panel because the panel .mqh is compiled into    |
//| the same indicator module (same as how LayerToggled calls          |
//| ObjectsDeleteAll directly, no round-trip through the main .mq5).   |
//+------------------------------------------------------------------+
void CVWAPZonesPanel::SetPlotVisible(const int plot_index, const bool visible)
{
   PlotIndexSetInteger(plot_index, PLOT_DRAW_TYPE, visible ? DRAW_LINE : DRAW_NONE);
   ChartRedraw(m_chart_id);
}

void CVWAPZonesPanel::OnChangeVwapLine(void)
{
   g_show_vwap_line = m_chk_vwap.Checked();
   SetPlotVisible(0, g_show_vwap_line); // buffer 0 = VWAP
}

void CVWAPZonesPanel::OnChangeBands(void)
{
   g_show_bands = m_chk_bands.Checked();
   SetPlotVisible(1, g_show_bands); // buffers 1-4 = Upper1/Lower1/Upper2/Lower2
   SetPlotVisible(2, g_show_bands);
   SetPlotVisible(3, g_show_bands);
   SetPlotVisible(4, g_show_bands);
}

void CVWAPZonesPanel::OnChangeZones(void)
{
   g_show_zones = m_chk_zones.Checked();
   LayerToggled("ZI_VWAP_ZONE_", g_show_zones);
}

void CVWAPZonesPanel::OnChangeTouch(void)
{
   int v = (int)m_spin_touch.Value();
   g_touch_band_request = v; // main .mq5 applies this via g_engine.SetTouchBand()
   m_lbl_touch_val.Text(v == 2 ? "2-sigma" : "1-sigma");
   g_panel_force_redraw = true;
   ChartRedraw(m_chart_id);
}

void CVWAPZonesPanel::OnChangeExh(void)
{
   int v = (int)m_spin_exh.Value();
   g_exhaustion_bars_request = v; // main .mq5 applies this via g_engine.SetExhaustionBars()
   ChartRedraw(m_chart_id);
}

void CVWAPZonesPanel::OnChangePush(void)
{
   g_alert_push = m_chk_push.Checked();
}

void CVWAPZonesPanel::OnChangeSound(void)
{
   g_alert_sound = m_chk_sound.Checked();
}

//+------------------------------------------------------------------+
EVENT_MAP_BEGIN(CVWAPZonesPanel)
   ON_EVENT(ON_CHANGE, m_chk_vwap,  OnChangeVwapLine)
   ON_EVENT(ON_CHANGE, m_chk_bands, OnChangeBands)
   ON_EVENT(ON_CHANGE, m_chk_zones, OnChangeZones)
   ON_EVENT(ON_CHANGE, m_spin_touch, OnChangeTouch)
   ON_EVENT(ON_CHANGE, m_spin_exh,   OnChangeExh)
   ON_EVENT(ON_CHANGE, m_chk_push,  OnChangePush)
   ON_EVENT(ON_CHANGE, m_chk_sound, OnChangeSound)
EVENT_MAP_END(CAppDialog)

#endif // VWAP_ZONES_PANEL_MQH
