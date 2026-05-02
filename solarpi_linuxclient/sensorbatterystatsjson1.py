"""
sensorbatterystatsjson1.py

Data source description:
- SolarPi side: Flask server at http://192.168.1.100:5000/solarpi/timeseries
  - Logs: ina44_v, ina44_i (12 V bus), ina45_v, ina45_i (5 V USB), and BME / TSL sensors.
- ESP8266 side: Flask server at http://192.168.1.100:5000/esp8266
  - Logs: bus_voltage_v, current_ma, power statistics for a 20 Ah 12 V battery bank.

What this script does:

1. Fetches timeseries data from both SolarPi and ESP8266 endpoints.
2. Joins them into a single DataFrame indexed by timestamp.
3. Computes daily statistics (mean, min, max, etc.) for:
   - 12 V solar bus (ina44_v, ina44_i)
   - 5 V USB bus (ina45_v, ina45_i)
   - 12 V battery bus (bus_voltage_v, esp_current_ma)
4. Integrates power (W) over time to get daily energy in Wh for:
   - solar_Wh   = 12 V bus (charging from solar)
   - usb5_Wh    = 5 V bus (load via USB)
   - battery_Wh = 12 V battery bus (net charge/discharge at the battery)
5. From battery_Wh, computes:
   - Delta SOC (ΔSOC): energy change relative to assumed battery capacity.
   - DoD (Depth of Discharge): only for discharge‑days, as % of capacity.
   - Running SOC estimate: starts at 60% and integrates daily Wh forward.
6. Prints:
   - a table of daily sensor statistics,
   - a combined SOC‑style table with Date, SOC, ΔSOC, battery_Wh, DoD, and comment,
   - a compact block of "DISCHARGE DAYS", showing DoD, avg/peak current, and Wh out.

Assumptions:
- Battery is nominally 20 Ah (≈ 240 Wh for 12 V) with STARTING_SOC_PCT = 60.0.
- Energy integration uses constant sample periods (solar_dt_h, esp_dt_h) computed from the data.
- The script operates on the last 21 days of data.
"""

import pandas as pd
import numpy as np
import requests

FLASK_SOLAR_URL = "http://192.168.1.100:5000/solarpi/timeseries"
FLASK_ESP8266_URL = "http://192.168.1.100:5000/esp8266"

# ==================== COLOR HELPERS FOR TERMINAL ====================
# Use if you want colored console output; works on most Linux/macOS terminals.

COLOR_RESET = "\033[0m"
COLOR_RED    = "\033[91m"   # Discharge, large negative spikes
COLOR_GREEN  = "\033[92m"   # Charging, normal behavior
COLOR_YELLOW = "\033[93m"   # Rainy‑day / high‑DoD day
COLOR_CYAN   = "\033[96m"   # Header / general positive data
COLOR_PURPLE = "\033[95m"   # Outliers / special annotations


def color_text(text: str, color: str) -> str:
    return f"{color}{text}{COLOR_RESET}"

# Helper to compute average sample period in seconds
def avg_sample_period_s(ts_index):
    dt = ts_index.to_series().diff()
    return dt.mean().total_seconds()


def fetch_json(url, source_name, timeout=10):
    print(f"Fetching data from {source_name}...")
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data)

        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            df = df.dropna(subset=['timestamp']).set_index('timestamp').sort_index()
        elif 'time' in df.columns:  # ESP8266 uses 'time'
            df['timestamp'] = pd.to_datetime(df['time'], errors='coerce')
            df = df.dropna(subset=['timestamp']).set_index('timestamp').sort_index()
        else:
            print(f"  ❌ No timestamp column in {source_name}")
            df.index = pd.to_datetime(range(len(df)))

        print(f"  ✅ Fetched {len(df)} records from {source_name}")
        return df
    except Exception as e:
        print(f"  ⚠️ Failed to fetch from {source_name}: {type(e).__name__}: {e}")
        return pd.DataFrame(index=pd.to_datetime([]))


# ==================== FETCH SENSOR DATA ====================
df_solar = fetch_json(FLASK_SOLAR_URL, "SolarPi main")
df_esp   = fetch_json(FLASK_ESP8266_URL, "ESP8266 battery monitor")

print("\nSOLAR COLUMNS :", sorted(df_solar.columns.tolist()))
print("ESP COLUMNS   :", sorted(df_esp.columns.tolist()))

# Combine SolarPi + ESP8266 by time; ESP more frequent, so ESP wins on duplicates
df = pd.concat([df_solar, df_esp])
df = df[~df.index.duplicated(keep='last')].sort_index()

# ==================== ENSURE core SolarPi channels exist ====================
for col in ['ina44_v', 'ina44_i', 'ina45_v', 'ina45_i']:
    if col not in df.columns:
        df[col] = np.nan

# ==================== ESP‑ONLY BUS CHANNELS ====================
# Keep bus_voltage_v and esp_current_ma as battery‑side only
if not df_esp.empty:
    if 'bus_voltage_v' in df_esp.columns:
        df['bus_voltage_v'] = df_esp['bus_voltage_v']
    else:
        df['bus_voltage_v'] = np.nan

    if 'current_a' in df_esp.columns:
        df['esp_current_ma'] = df_esp['current_a'] * 1000
    elif 'current_ma' in df_esp.columns:
        df['esp_current_ma'] = df_esp['current_ma']
    else:
        df['esp_current_ma'] = np.nan
else:
    df['bus_voltage_v'] = np.nan
    df['esp_current_ma'] = np.nan


# ==================== DAILY STATS (only on last 21 days) ====================
cols_to_analyze = [
    'ina44_v', 'ina44_i',
    'ina45_v', 'ina45_i',
    'bus_voltage_v',
    'esp_current_ma'
]

days_back = 21
cutoff = df.index.max().normalize() - pd.Timedelta(days=days_back)
df_recent = df[df.index >= cutoff]

daily = df_recent[cols_to_analyze].groupby(df_recent.index.date)
daily_stats_mi = daily.agg([
    ('mean', 'mean'),
    ('std', 'std'),
    ('min', 'min'),
    ('max', 'max')
]).round(3)

# Optional 3‑sigma for currents (debug, not printed)
for col in ['ina44_i', 'ina45_i', 'esp_current_ma']:
    mean_name = (col, 'mean')
    std_name  = (col, 'std')
    if mean_name in daily_stats_mi.columns and std_name in daily_stats_mi.columns:
        daily_stats_mi[(col, '3sigma_lo')] = daily_stats_mi[mean_name] - 3 * daily_stats_mi[std_name]
        daily_stats_mi[(col, '3sigma_hi')] = daily_stats_mi[mean_name] + 3 * daily_stats_mi[std_name]

daily_stats = daily_stats_mi.copy()
daily_stats.columns = ['_'.join(map(str, c)) for c in daily_stats.columns]
# Drop 3sigma columns for printing
cols_to_keep = [c for c in daily_stats.columns
                if not c.endswith('_3sigma_lo') and not c.endswith('_3sigma_hi')]
daily_stats = daily_stats[cols_to_keep]


# ==================== ENERGY INTEGRALS: solar_Wh, usb5_Wh, battery_Wh ====================
solar_period_s = avg_sample_period_s(df_solar.index) if not df_solar.empty else 1.0
esp_period_s   = avg_sample_period_s(df_esp.index)   if not df_esp.empty   else 1.0

solar_dt_h = solar_period_s / 3600.0
esp_dt_h   = esp_period_s   / 3600.0

print(f"\nAverage SolarPi sample period: {solar_period_s:.2f} s")
print(f"Average ESP8266 sample period: {esp_period_s:.2f} s")

df['solar_power_w']   = df['ina44_v']  * df['ina44_i'] / 1000     # 12‑V bus
df['usb5_power_w']    = df['ina45_v']  * df['ina45_i'] / 1000     # 5‑V rail
df['battery_power_w'] = df['bus_voltage_v'] * df['esp_current_ma'] / 1000   # 12‑V ESP bus

daily_energy = df.groupby(df.index.date).agg(
    solar_Wh=('solar_power_w',   lambda x: (x * solar_dt_h).sum()),
    usb5_Wh=('usb5_power_w',    lambda x: (x * solar_dt_h).sum()),
    battery_Wh=('battery_power_w', lambda x: (x * esp_dt_h).sum()),
).round(3)

daily_stats = daily_stats.join(daily_energy)


# ==================== KEY COLUMNS TO DISPLAY ====================
key_cols = [
    'ina44_v_mean', 'ina44_v_min', 'ina44_v_max',
    'ina44_i_mean', 'ina44_i_min', 'ina44_i_max',
    'ina45_v_mean', 'ina45_v_min', 'ina45_v_max',
    'ina45_i_mean', 'ina45_i_min', 'ina45_i_max',
    'bus_voltage_v_mean', 'bus_voltage_v_min', 'bus_voltage_v_max',
    'esp_current_ma_mean', 'esp_current_ma_min', 'esp_current_ma_max',
    'solar_Wh', 'usb5_Wh', 'battery_Wh'
]

print("\n" + "=" * 80)
print("📊 DAILY SENSOR STATISTICS (last 21 days)")
print("=" * 80)

available = [c for c in key_cols if c in daily_stats.columns]
if available:
    print(daily_stats[available].round(3).to_string())
else:
    print("No key columns found. Available columns:")
    print(daily_stats.columns.tolist())


# =============== 🛠️ ENSURE `daily` is a DataFrame for SOC section ===============
daily = daily_stats[available].copy()   # now a plain DataFrame, not GroupBy


# ========================================================================================================================
# 📊 DAILY BATTERY SOC‑STYLE SUMMARY (last 21 days)
# ========================================================================================================================
BATTERY_CAPACITY_Wh = 240.0      # 20 Ah @ ~12 V  => about 240 Wh
STARTING_SOC_PCT    = 60.0       # your target SOC at start of period

print("\n" + "=" * 120)
print("📊 DAILY BATTERY SOC‑STYLE SUMMARY (last 21 days)")
print("=" * 120)

if 'battery_Wh' in daily.columns:
    daily = daily.copy()

    # Add SOC‑related columns
    daily['battery_Wh'] = daily['battery_Wh'].fillna(0)
    daily['soc_delta_pct'] = (daily['battery_Wh'] / BATTERY_CAPACITY_Wh) * 100
    # DoD only on discharge days, as percentage of capacity
    daily['dod_pct'] = daily['battery_Wh'].clip(upper=0).abs() / BATTERY_CAPACITY_Wh * 100

    # Running SOC trace (starting from 60%)
    soc_wh = STARTING_SOC_PCT / 100.0 * BATTERY_CAPACITY_Wh
    soc_pct_trace = []
    for idx, row in daily.iterrows():
        soc_wh += row['battery_Wh']
        soc_pct = max(0.0, min(100.0, soc_wh / BATTERY_CAPACITY_Wh * 100))
        soc_pct_trace.append(soc_pct)
    daily['soc_pct'] = soc_pct_trace

    # Print aligned table with Date and SOC info
    print(f"{color_text('Date', COLOR_CYAN):<12} "
          f"{color_text('SOC (%)', COLOR_CYAN):<8} "
          f"{color_text('ΔSOC (%)', COLOR_CYAN):<10} "
          f"{color_text('battery_Wh', COLOR_CYAN):<12} "
          f"{color_text('DoD (%)', COLOR_CYAN):<8} "
          f"{color_text('Comment', COLOR_CYAN)}")
    print("-" * 120)

    for idx, row in daily.iterrows():
        soc = row['soc_pct']
        delta = row['soc_delta_pct']
        bwh = row['battery_Wh']
        dod = row['dod_pct']

        if bwh >= 0:
            comment = f"Charging (gain {bwh:.2f} Wh)"
            line_color = COLOR_GREEN
        else:
            comment = f"Discharge (loss {-bwh:.2f} Wh)"
            # Highlight heavy‑discharge days as yellow / red
            if abs(dod) > 5.0:
                line_color = COLOR_YELLOW  # e.g., 5%+ DoD
            elif abs(dod) > 10.0:
                line_color = COLOR_RED  # large discharge
            else:
                line_color = COLOR_RED

        # Keep Date and SOC neutral, color only the dynamic part
        date_str = str(idx)
        soc_str = f"{soc:<8.1f}"
        delta_str = f"{delta:<10.2f}"
        bwh_str = f"{bwh:<12.3f}"
        dod_str = f"{dod:<8.1f}"

        print(
            f"{date_str:<12} "
            f"{soc_str:<8} "
            f"{delta_str:<10} "
            f"{color_text(bwh_str, line_color):<12} "
            f"{color_text(dod_str, line_color):<8} "
            f"{color_text(comment, line_color)}"
        )


    # ==================== DISCHARGE DAYS (net loss from battery) ====================
    print("\n" + "=" * 100)
    print("📊 DISCHARGE DAYS (net loss from battery)")
    print("=" * 100)

    discharge_mask = daily['battery_Wh'] < 0
    discharge_rows = daily[discharge_mask]

    for idx, row in discharge_rows.iterrows():
        avg_current = row['esp_current_ma_mean']
        min_current = row['esp_current_ma_min']
        bwh = row['battery_Wh']
        dod = row['dod_pct']
        print(f"{idx} : DoD ≈ {dod:.2f}%  → {bwh:.2f} Wh out, "
              f"avg current = {avg_current:.1f} mA, peak discharge = {min_current:.1f} mA")
else:
    print("battery_Wh column not found; cannot compute SOC‑style summary.")