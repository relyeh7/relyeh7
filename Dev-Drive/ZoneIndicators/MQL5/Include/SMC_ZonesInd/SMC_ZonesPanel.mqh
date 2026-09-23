//+------------------------------------------------------------------+
//| SMC_ZonesPanel.mqh - CAppDialog control panel for SMC_ZonesInd    |
//| Pattern copied from H:\Dev-Drive\SMC\SMC_Indicator.mq5            |
//| (CSMCMtfPanel): corner anchoring, dark-background checkboxes,     |
//| timer-driven refresh, caption-X survival. UI only - no detection. |
//+------------------------------------------------------------------+
#ifndef SMC_ZONES_PANEL_MQH
#define SMC_ZONES_PANEL_MQH

#property strict

#include <Controls\Dialog.mqh>
#include <Controls\Panel.mqh>
#include <Controls\Label.mqh>
#include <Controls\Button.mqh>
#include <Controls\CheckBox.mqh>
#include <Controls\SpinEdit.mqh>

//--- Runtime-mutable flags the panel owns. Drawing/alert code reads ONLY these,
//--- never the Inp* inputs directly (seeded once from Inp* in OnInit).
bool g_show_ob          = true;
bool g_show_fvg         = true;
bool g_show_sweep       = true;
bool g_show_pd          = true;
int  g_min_confluence   = 2;
bool g_alert_push       = true;
bool g_alert_sound      = true;
bool g_panel_force_redraw = false; // set true when a layer is re-enabled

#define SMCP_CLR_BG      C'16,18,24'
#define SMCP_CLR_HDR     C'25,45,80'
#define SMCP_CLR_LBL     clrWhite
#define SMCP_DLG_W       260
#define SMCP_IND         10
#define SMCP_HDR_H       20
#define SMCP_ROW_H       18
#define SMCP_CHK_H       20
#define SMCP_GAP         6
#define SMCP_CHK_W       120

//+------------------------------------------------------------------+
//| Resolve a corner anchor into CAppDialog's absolute-pixel space    |
//+------------------------------------------------------------------+
void SMCP_ResolveOrigin(const int corner, const int off_x, const int off_y,
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
//| CSMCDarkCheckBox - CCheckBox that survives a dark panel background|
//+------------------------------------------------------------------+
class CSMCDarkCheckBox : public CCheckBox
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
//| CSMCZonesPanel                                                    |
//+------------------------------------------------------------------+
class CSMCZonesPanel : public CAppDialog
{
private:
   CPanel            m_bg;
   CPanel            m_bar_layers;
   CLabel            m_lbl_layers;
   CSMCDarkCheckBox  m_chk_ob;
   CSMCDarkCheckBox  m_chk_fvg;
   CSMCDarkCheckBox  m_chk_sweep;
   CSMCDarkCheckBox  m_chk_pd;
   CPanel            m_bar_conf;
   CLabel            m_lbl_conf;
   CLabel            m_lbl_conf_val;
   CSpinEdit         m_spin_conf;
   CPanel            m_bar_alerts;
   CLabel            m_lbl_alerts;
   CSMCDarkCheckBox  m_chk_push;
   CSMCDarkCheckBox  m_chk_sound;

   int               m_client_h;
   int               m_y_layers, m_y_chk1, m_y_chk2, m_y_conf, m_y_alerts, m_y_chk3;

public:
                     CSMCZonesPanel(void) : m_client_h(0) {}
                    ~CSMCZonesPanel(void) {}

   bool              CreateAt(const long chart, const int subwin, const int corner,
                               const int off_x, const int off_y);
   virtual bool      OnEvent(const int id, const long &lparam, const double &dparam, const string &sparam);
   void              Refresh(void);

protected:
   void              Layout(void);
   bool              CreateControls(void);
   bool              MakeLabel(CLabel &l, const string id, const int x, const int y, const int w,
                                const string text, const color clr, const int size = 8,
                                const string font = "Segoe UI");
   bool              MakeBar(CPanel &p, const string id, const int x, const int y, const int w,
                              const int h, const color clr);
   bool              MakeCheck(CSMCDarkCheckBox &c, const string id, const int x, const int y,
                                const int w, const string text, const bool checked);
   void              LayerToggled(const string layer_prefix, const bool now_on);

   void              OnChangeOB(void);
   void              OnChangeFVG(void);
   void              OnChangeSweep(void);
   void              OnChangePD(void);
   void              OnChangeConfluence(void);
   void              OnChangePush(void);
   void              OnChangeSound(void);
};

//+------------------------------------------------------------------+
void CSMCZonesPanel::Layout(void)
{
   int y = SMCP_IND;
   m_y_layers = y; y += SMCP_HDR_H + SMCP_GAP;
   m_y_chk1   = y; y += SMCP_CHK_H;
   m_y_chk2   = y; y += SMCP_CHK_H + SMCP_GAP;
   m_y_conf   = y; y += SMCP_HDR_H + SMCP_GAP;
   m_y_alerts = y; y += SMCP_HDR_H + SMCP_GAP;
   m_y_chk3   = y; y += SMCP_CHK_H;
   m_client_h = y + SMCP_IND;
}

//+------------------------------------------------------------------+
bool CSMCZonesPanel::MakeLabel(CLabel &l, const string id, const int x, const int y, const int w,
                                const string text, const color clr, const int size, const string font)
{
   if(!l.Create(m_chart_id, m_name + id, m_subwin, x, y, x + w, y + SMCP_ROW_H)) return false;
   if(!Add(l)) return false;
   l.Font(font);
   l.FontSize(size);
   l.Color(clr);
   l.Text(text);
   return true;
}

bool CSMCZonesPanel::MakeBar(CPanel &p, const string id, const int x, const int y, const int w,
                              const int h, const color clr)
{
   if(!p.Create(m_chart_id, m_name + id, m_subwin, x, y, x + w, y + h)) return false;
   if(!Add(p)) return false;
   p.ColorBackground(clr);
   p.ColorBorder(clr);
   p.BorderType(BORDER_FLAT);
   return true;
}

bool CSMCZonesPanel::MakeCheck(CSMCDarkCheckBox &c, const string id, const int x, const int y,
                                const int w, const string text, const bool checked)
{
   if(!c.Create(m_chart_id, m_name + id, m_subwin, x, y, x + w, y + SMCP_CHK_H)) return false;
   if(!Add(c)) return false;
   c.Text(text);
   c.Checked(checked);
   c.Recolor(SMCP_CLR_BG, clrWhite); // must run after Create: the caption object doesn't exist before it
   return true;
}

//+------------------------------------------------------------------+
bool CSMCZonesPanel::CreateAt(const long chart, const int subwin, const int corner,
                               const int off_x, const int off_y)
{
   Layout();
   int dlg_h = m_client_h + 28;
   int x, y;
   SMCP_ResolveOrigin(corner, off_x, off_y, SMCP_DLG_W, dlg_h, x, y);

   if(!CAppDialog::Create(chart, "SMCZones", subwin, x, y, x + SMCP_DLG_W, y + dlg_h))
      return false;

   Caption("SMC ZONES");

   if(!CreateControls()) return false;

   Refresh();
   return true;
}

bool CSMCZonesPanel::CreateControls(void)
{
   int full_w = SMCP_DLG_W - 12 - 2 * SMCP_IND;

   if(!MakeBar(m_bg, "BG", 0, 0, SMCP_DLG_W - 12, m_client_h, SMCP_CLR_BG)) return false;

   //--- Layer toggles
   if(!MakeBar(m_bar_layers, "BarLay", SMCP_IND, m_y_layers, full_w, SMCP_HDR_H, SMCP_CLR_HDR)) return false;
   if(!MakeLabel(m_lbl_layers, "LblLay", SMCP_IND + 6, m_y_layers, full_w - 6, "ZONE LAYERS", clrWhite, 7, "Segoe UI Semibold"))
      return false;

   int col2_x = SMCP_IND + SMCP_CHK_W + 10;
   if(!MakeCheck(m_chk_ob,    "ChkOb",  SMCP_IND, m_y_chk1, SMCP_CHK_W, "Order Blocks",  g_show_ob))    return false;
   if(!MakeCheck(m_chk_fvg,   "ChkFvg", col2_x,   m_y_chk1, SMCP_CHK_W, "Fair Value Gap", g_show_fvg))  return false;
   if(!MakeCheck(m_chk_sweep, "ChkSwp", SMCP_IND, m_y_chk2, SMCP_CHK_W, "Liquidity Sweep", g_show_sweep)) return false;
   if(!MakeCheck(m_chk_pd,    "ChkPd",  col2_x,   m_y_chk2, SMCP_CHK_W, "Premium/Discount", g_show_pd))  return false;

   //--- Confluence threshold
   if(!MakeBar(m_bar_conf, "BarConf", SMCP_IND, m_y_conf, full_w, SMCP_HDR_H, SMCP_CLR_HDR)) return false;
   if(!MakeLabel(m_lbl_conf, "LblConf", SMCP_IND + 6, m_y_conf, 150, "MIN CONFLUENCE (A+)", clrWhite, 7, "Segoe UI Semibold"))
      return false;
   if(!m_spin_conf.Create(m_chart_id, m_name + "SpinConf", m_subwin,
                           SMCP_IND + full_w - 60, m_y_conf, SMCP_IND + full_w - 6, m_y_conf + SMCP_HDR_H))
      return false;
   if(!Add(m_spin_conf)) return false;
   m_spin_conf.MinValue(1);
   m_spin_conf.MaxValue(5);
   m_spin_conf.Value(g_min_confluence);

   //--- Alerts
   if(!MakeBar(m_bar_alerts, "BarAl", SMCP_IND, m_y_alerts, full_w, SMCP_HDR_H, SMCP_CLR_HDR)) return false;
   if(!MakeLabel(m_lbl_alerts, "LblAl", SMCP_IND + 6, m_y_alerts, full_w - 6, "ALERTS", clrWhite, 7, "Segoe UI Semibold"))
      return false;
   if(!MakeCheck(m_chk_push,  "ChkPush",  SMCP_IND, m_y_chk3, SMCP_CHK_W, "Push notification", g_alert_push))  return false;
   if(!MakeCheck(m_chk_sound, "ChkSound", col2_x,   m_y_chk3, SMCP_CHK_W, "Sound alert",        g_alert_sound)) return false;

   return true;
}

//+------------------------------------------------------------------+
void CSMCZonesPanel::Refresh(void)
{
   //--- Panel may have been closed with the caption X; the program (and its
   //--- timer) keeps running, so guard against writing to dead controls.
   if(ObjectFind(m_chart_id, m_chk_ob.Name()) < 0) return;
   ChartRedraw(m_chart_id);
}

//+------------------------------------------------------------------+
void CSMCZonesPanel::LayerToggled(const string layer_prefix, const bool now_on)
{
   if(!now_on && layer_prefix != "")
      ObjectsDeleteAll(0, layer_prefix);
   else
      g_panel_force_redraw = true; // re-enabled: next OnCalculate tick repaints it from live zones
   ChartRedraw(m_chart_id);
}

void CSMCZonesPanel::OnChangeOB(void)
{
   g_show_ob = m_chk_ob.Checked();
   LayerToggled("ZI_SMC_OB_", g_show_ob);
}

void CSMCZonesPanel::OnChangeFVG(void)
{
   g_show_fvg = m_chk_fvg.Checked();
   LayerToggled("ZI_SMC_FVG_", g_show_fvg);
}

void CSMCZonesPanel::OnChangeSweep(void)
{
   g_show_sweep = m_chk_sweep.Checked();
   LayerToggled("ZI_SMC_SWEEP_", g_show_sweep);
}

void CSMCZonesPanel::OnChangePD(void)
{
   g_show_pd = m_chk_pd.Checked();
   LayerToggled("ZI_SMC_PD_", g_show_pd);
}

void CSMCZonesPanel::OnChangeConfluence(void)
{
   g_min_confluence = (int)m_spin_conf.Value();
   g_panel_force_redraw = true;
   ChartRedraw(m_chart_id);
}

void CSMCZonesPanel::OnChangePush(void)
{
   g_alert_push = m_chk_push.Checked();
}

void CSMCZonesPanel::OnChangeSound(void)
{
   g_alert_sound = m_chk_sound.Checked();
}

//+------------------------------------------------------------------+
EVENT_MAP_BEGIN(CSMCZonesPanel)
   ON_EVENT(ON_CHANGE, m_chk_ob,    OnChangeOB)
   ON_EVENT(ON_CHANGE, m_chk_fvg,   OnChangeFVG)
   ON_EVENT(ON_CHANGE, m_chk_sweep, OnChangeSweep)
   ON_EVENT(ON_CHANGE, m_chk_pd,    OnChangePD)
   ON_EVENT(ON_CHANGE, m_spin_conf, OnChangeConfluence)
   ON_EVENT(ON_CHANGE, m_chk_push,  OnChangePush)
   ON_EVENT(ON_CHANGE, m_chk_sound, OnChangeSound)
EVENT_MAP_END(CAppDialog)

#endif // SMC_ZONES_PANEL_MQH
