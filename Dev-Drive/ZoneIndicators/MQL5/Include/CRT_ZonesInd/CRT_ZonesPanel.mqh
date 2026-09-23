//+------------------------------------------------------------------+
//| CRT_ZonesPanel.mqh - CAppDialog control panel for CRT_ZonesInd    |
//| Pattern copied from ZoneIndicators\MQL5\Include\SMC_ZonesInd\     |
//| SMC_ZonesPanel.mqh (itself from H:\Dev-Drive\SMC\SMC_Indicator.   |
//| mq5's CSMCMtfPanel): corner anchoring, dark-background checkboxes,|
//| timer-driven refresh, caption-X survival. UI only - no detection. |
//+------------------------------------------------------------------+
#ifndef CRT_ZONES_PANEL_MQH
#define CRT_ZONES_PANEL_MQH

#property strict

#include <Controls\Dialog.mqh>
#include <Controls\Panel.mqh>
#include <Controls\Label.mqh>
#include <Controls\Button.mqh>
#include <Controls\CheckBox.mqh>
#include <Controls\SpinEdit.mqh>
#include <CRT_ZonesInd\CRT_ZonesEngine.mqh>

//--- Runtime-mutable flags the panel owns. Drawing/alert code reads ONLY these,
//--- never the Inp* inputs directly (seeded once from Inp* in OnInit).
bool g_show_zones        = true;
bool g_show_range        = true;
int  g_min_sweep_strength = 2;
bool g_alert_push        = true;
bool g_alert_sound       = true;
bool g_panel_force_redraw = false; // set true when a layer is re-enabled or range mode changes

//--- Set by the panel's range-mode spin edit; the main .mq5 reads this once per
//--- tick and calls g_engine.ResetRangeMode() when it differs from the engine's
//--- own mode - the panel cannot reach the engine object directly.
int  g_range_mode_request = -1; // -1 = no pending change

#define CRTP_CLR_BG      C'16,18,24'
#define CRTP_CLR_HDR     C'25,45,80'
#define CRTP_CLR_LBL     clrWhite
#define CRTP_DLG_W       260
#define CRTP_IND         10
#define CRTP_HDR_H       20
#define CRTP_ROW_H       18
#define CRTP_CHK_H       20
#define CRTP_GAP         6
#define CRTP_CHK_W       120

//+------------------------------------------------------------------+
//| Resolve a corner anchor into CAppDialog's absolute-pixel space    |
//+------------------------------------------------------------------+
void CRTP_ResolveOrigin(const int corner, const int off_x, const int off_y,
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
//| CCRTDarkCheckBox - CCheckBox that survives a dark panel background|
//+------------------------------------------------------------------+
class CCRTDarkCheckBox : public CCheckBox
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
//| CCRTZonesPanel                                                    |
//+------------------------------------------------------------------+
class CCRTZonesPanel : public CAppDialog
{
private:
   CPanel            m_bg;
   CPanel            m_bar_mode;
   CLabel            m_lbl_mode;
   CLabel            m_lbl_mode_val;
   CSpinEdit         m_spin_mode;
   CPanel            m_bar_layers;
   CLabel            m_lbl_layers;
   CCRTDarkCheckBox  m_chk_zones;
   CCRTDarkCheckBox  m_chk_range;
   CPanel            m_bar_strength;
   CLabel            m_lbl_strength;
   CSpinEdit         m_spin_strength;
   CPanel            m_bar_alerts;
   CLabel            m_lbl_alerts;
   CCRTDarkCheckBox  m_chk_push;
   CCRTDarkCheckBox  m_chk_sound;

   int               m_client_h;
   int               m_y_mode, m_y_layers, m_y_chk1, m_y_strength, m_y_alerts, m_y_chk2;

public:
                     CCRTZonesPanel(void) : m_client_h(0) {}
                    ~CCRTZonesPanel(void) {}

   bool              CreateAt(const long chart, const int subwin, const int corner,
                               const int off_x, const int off_y, const ENUM_CRT_RANGE_MODE initialMode);
   virtual bool      OnEvent(const int id, const long &lparam, const double &dparam, const string &sparam);
   void              Refresh(void);

protected:
   void              Layout(void);
   bool              CreateControls(const ENUM_CRT_RANGE_MODE initialMode);
   bool              MakeLabel(CLabel &l, const string id, const int x, const int y, const int w,
                                const string text, const color clr, const int size = 8,
                                const string font = "Segoe UI");
   bool              MakeBar(CPanel &p, const string id, const int x, const int y, const int w,
                              const int h, const color clr);
   bool              MakeCheck(CCRTDarkCheckBox &c, const string id, const int x, const int y,
                                const int w, const string text, const bool checked);
   void              LayerToggled(const string layer_prefix, const bool now_on);
   string            ModeText(const int v);

   void              OnChangeMode(void);
   void              OnChangeZones(void);
   void              OnChangeRange(void);
   void              OnChangeStrength(void);
   void              OnChangePush(void);
   void              OnChangeSound(void);
};

//+------------------------------------------------------------------+
void CCRTZonesPanel::Layout(void)
{
   int y = CRTP_IND;
   m_y_mode     = y; y += CRTP_HDR_H + CRTP_GAP;
   m_y_layers   = y; y += CRTP_HDR_H + CRTP_GAP;
   m_y_chk1     = y; y += CRTP_CHK_H + CRTP_GAP;
   m_y_strength = y; y += CRTP_HDR_H + CRTP_GAP;
   m_y_alerts   = y; y += CRTP_HDR_H + CRTP_GAP;
   m_y_chk2     = y; y += CRTP_CHK_H;
   m_client_h   = y + CRTP_IND;
}

//+------------------------------------------------------------------+
bool CCRTZonesPanel::MakeLabel(CLabel &l, const string id, const int x, const int y, const int w,
                                const string text, const color clr, const int size, const string font)
{
   if(!l.Create(m_chart_id, m_name + id, m_subwin, x, y, x + w, y + CRTP_ROW_H)) return false;
   if(!Add(l)) return false;
   l.Font(font);
   l.FontSize(size);
   l.Color(clr);
   l.Text(text);
   return true;
}

bool CCRTZonesPanel::MakeBar(CPanel &p, const string id, const int x, const int y, const int w,
                              const int h, const color clr)
{
   if(!p.Create(m_chart_id, m_name + id, m_subwin, x, y, x + w, y + h)) return false;
   if(!Add(p)) return false;
   p.ColorBackground(clr);
   p.ColorBorder(clr);
   p.BorderType(BORDER_FLAT);
   return true;
}

bool CCRTZonesPanel::MakeCheck(CCRTDarkCheckBox &c, const string id, const int x, const int y,
                                const int w, const string text, const bool checked)
{
   if(!c.Create(m_chart_id, m_name + id, m_subwin, x, y, x + w, y + CRTP_CHK_H)) return false;
   if(!Add(c)) return false;
   c.Text(text);
   c.Checked(checked);
   c.Recolor(CRTP_CLR_BG, clrWhite); // must run after Create: the caption object doesn't exist before it
   return true;
}

string CCRTZonesPanel::ModeText(const int v)
{
   if(v == (int)CRT_RANGE_DAILY)   return "DAILY";
   if(v == (int)CRT_RANGE_H4)      return "4H";
   return "SESSION";
}

//+------------------------------------------------------------------+
bool CCRTZonesPanel::CreateAt(const long chart, const int subwin, const int corner,
                               const int off_x, const int off_y, const ENUM_CRT_RANGE_MODE initialMode)
{
   Layout();
   int dlg_h = m_client_h + 28;
   int x, y;
   CRTP_ResolveOrigin(corner, off_x, off_y, CRTP_DLG_W, dlg_h, x, y);

   if(!CAppDialog::Create(chart, "CRTZones", subwin, x, y, x + CRTP_DLG_W, y + dlg_h))
      return false;

   Caption("CRT ZONES");

   if(!CreateControls(initialMode)) return false;

   Refresh();
   return true;
}

bool CCRTZonesPanel::CreateControls(const ENUM_CRT_RANGE_MODE initialMode)
{
   int full_w = CRTP_DLG_W - 12 - 2 * CRTP_IND;

   if(!MakeBar(m_bg, "BG", 0, 0, CRTP_DLG_W - 12, m_client_h, CRTP_CLR_BG)) return false;

   //--- Range mode selector
   if(!MakeBar(m_bar_mode, "BarMode", CRTP_IND, m_y_mode, full_w, CRTP_HDR_H, CRTP_CLR_HDR)) return false;
   if(!MakeLabel(m_lbl_mode, "LblMode", CRTP_IND + 6, m_y_mode, 90, "RANGE", clrWhite, 7, "Segoe UI Semibold"))
      return false;
   if(!m_spin_mode.Create(m_chart_id, m_name + "SpinMode", m_subwin,
                           CRTP_IND + full_w - 60, m_y_mode, CRTP_IND + full_w - 6, m_y_mode + CRTP_HDR_H))
      return false;
   if(!Add(m_spin_mode)) return false;
   m_spin_mode.MinValue(0);
   m_spin_mode.MaxValue(2);
   m_spin_mode.Value((int)initialMode);
   if(!MakeLabel(m_lbl_mode_val, "LblModeVal", CRTP_IND + 90, m_y_mode, full_w - 90 - 62,
                 ModeText((int)initialMode), clrSilver, 7))
      return false;

   //--- Layer toggles
   if(!MakeBar(m_bar_layers, "BarLay", CRTP_IND, m_y_layers, full_w, CRTP_HDR_H, CRTP_CLR_HDR)) return false;
   if(!MakeLabel(m_lbl_layers, "LblLay", CRTP_IND + 6, m_y_layers, full_w - 6, "ZONE LAYERS", clrWhite, 7, "Segoe UI Semibold"))
      return false;

   int col2_x = CRTP_IND + CRTP_CHK_W + 10;
   if(!MakeCheck(m_chk_zones, "ChkZones", CRTP_IND, m_y_chk1, CRTP_CHK_W, "CRT Zones",      g_show_zones)) return false;
   if(!MakeCheck(m_chk_range, "ChkRange", col2_x,   m_y_chk1, CRTP_CHK_W, "Reference Range", g_show_range)) return false;

   //--- Min strength for A+ highlight
   if(!MakeBar(m_bar_strength, "BarStr", CRTP_IND, m_y_strength, full_w, CRTP_HDR_H, CRTP_CLR_HDR)) return false;
   if(!MakeLabel(m_lbl_strength, "LblStr", CRTP_IND + 6, m_y_strength, 170, "MIN SWEEP STRENGTH (A+)", clrWhite, 7, "Segoe UI Semibold"))
      return false;
   if(!m_spin_strength.Create(m_chart_id, m_name + "SpinStr", m_subwin,
                               CRTP_IND + full_w - 60, m_y_strength, CRTP_IND + full_w - 6, m_y_strength + CRTP_HDR_H))
      return false;
   if(!Add(m_spin_strength)) return false;
   m_spin_strength.MinValue(1);
   m_spin_strength.MaxValue(3);
   m_spin_strength.Value(g_min_sweep_strength);

   //--- Alerts
   if(!MakeBar(m_bar_alerts, "BarAl", CRTP_IND, m_y_alerts, full_w, CRTP_HDR_H, CRTP_CLR_HDR)) return false;
   if(!MakeLabel(m_lbl_alerts, "LblAl", CRTP_IND + 6, m_y_alerts, full_w - 6, "ALERTS", clrWhite, 7, "Segoe UI Semibold"))
      return false;
   if(!MakeCheck(m_chk_push,  "ChkPush",  CRTP_IND, m_y_chk2, CRTP_CHK_W, "Push notification", g_alert_push))  return false;
   if(!MakeCheck(m_chk_sound, "ChkSound", col2_x,   m_y_chk2, CRTP_CHK_W, "Sound alert",        g_alert_sound)) return false;

   return true;
}

//+------------------------------------------------------------------+
void CCRTZonesPanel::Refresh(void)
{
   //--- Panel may have been closed with the caption X; the program (and its
   //--- timer) keeps running, so guard against writing to dead controls.
   if(ObjectFind(m_chart_id, m_chk_zones.Name()) < 0) return;
   ChartRedraw(m_chart_id);
}

//+------------------------------------------------------------------+
void CCRTZonesPanel::LayerToggled(const string layer_prefix, const bool now_on)
{
   if(!now_on && layer_prefix != "")
      ObjectsDeleteAll(0, layer_prefix);
   else
      g_panel_force_redraw = true; // re-enabled: next OnCalculate tick repaints it from live zones
   ChartRedraw(m_chart_id);
}

void CCRTZonesPanel::OnChangeMode(void)
{
   int v = (int)m_spin_mode.Value();
   g_range_mode_request = v; // main .mq5 applies this via g_engine.ResetRangeMode()
   m_lbl_mode_val.Text(ModeText(v));
   g_panel_force_redraw = true;
   ChartRedraw(m_chart_id);
}

void CCRTZonesPanel::OnChangeZones(void)
{
   g_show_zones = m_chk_zones.Checked();
   LayerToggled("ZI_CRT_ZONE_", g_show_zones);
}

void CCRTZonesPanel::OnChangeRange(void)
{
   g_show_range = m_chk_range.Checked();
   LayerToggled("ZI_CRT_RANGE_", g_show_range);
}

void CCRTZonesPanel::OnChangeStrength(void)
{
   g_min_sweep_strength = (int)m_spin_strength.Value();
   g_panel_force_redraw = true;
   ChartRedraw(m_chart_id);
}

void CCRTZonesPanel::OnChangePush(void)
{
   g_alert_push = m_chk_push.Checked();
}

void CCRTZonesPanel::OnChangeSound(void)
{
   g_alert_sound = m_chk_sound.Checked();
}

//+------------------------------------------------------------------+
EVENT_MAP_BEGIN(CCRTZonesPanel)
   ON_EVENT(ON_CHANGE, m_spin_mode,     OnChangeMode)
   ON_EVENT(ON_CHANGE, m_chk_zones,     OnChangeZones)
   ON_EVENT(ON_CHANGE, m_chk_range,     OnChangeRange)
   ON_EVENT(ON_CHANGE, m_spin_strength, OnChangeStrength)
   ON_EVENT(ON_CHANGE, m_chk_push,      OnChangePush)
   ON_EVENT(ON_CHANGE, m_chk_sound,     OnChangeSound)
EVENT_MAP_END(CAppDialog)

#endif // CRT_ZONES_PANEL_MQH
