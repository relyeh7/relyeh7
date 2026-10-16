//+------------------------------------------------------------------+
//| ZI_Common.mqh — shared types for the Zone Indicators suite       |
//+------------------------------------------------------------------+
#ifndef ZI_COMMON_MQH
#define ZI_COMMON_MQH

#property strict

enum ENUM_ZI_TYPE { ZI_BUY, ZI_SELL };

struct ZI_Zone
{
   double     price_hi;
   double     price_lo;
   ENUM_ZI_TYPE type;
   int        strength;
   datetime   bar_time;
   bool       mitigated;
   string     label;
};

// Fires Alert()+SendNotification() with per-bar throttling.
// last_alert_bar_time is caller-owned state (one per zone-kind/direction).
void ZI_Alert(const string message, const bool push_enabled,
              const bool sound_enabled, datetime &last_alert_bar_time,
              const datetime current_bar_time)
{
   if(current_bar_time == last_alert_bar_time) return;
   last_alert_bar_time = current_bar_time;
   if(sound_enabled) Alert(message);
   if(push_enabled)  SendNotification(message);
}

#endif
