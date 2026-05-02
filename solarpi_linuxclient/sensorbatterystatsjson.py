# version 7.0 – Daily buck min/max, temperature min/max/avg, and requested columns
import pandas as pd
import numpy as np
import requests
import warnings

warnings.filterwarnings("ignore")
pd.set_option('future.no_silent_downcasting', True)

# ====================== PARAMETERS ======================
BATTERY_AH = 20.0
V_IGNORE_FOR_TRENDS = 3.0
V_CRITICAL = 9.3
ESP8266_START_DATE = pd.Timestamp("2026-03-25").normalize()
ENGINEERING_CHANGE_DATES = [
    pd.Timestamp("2026-03-22").normalize(),
    pd.Timestamp("2026-03-24").normalize(),
    pd.Timestamp("2026-03-25").normalize(),
]
lifepo4_ocv_table = {
    10.0: 0, 11.8: 5, 12.0: 10, 12.1: 20, 12.2: 30, 12.3: 40,
    12.4: 50, 12.5: 60, 12.6: 70, 12.8: 80, 13.0: 90,
    13.2: 95, 13.6: 99, 13.8: 100,
}
ocv_v = sorted(lifepo4_ocv_table.keys())
ocv_s = [lifepo4_ocv_table[v] for v in ocv_v]

MAINTENANCE_EVENTS = [
    {"date": "2026-03-09", "event": "HDC1000 → BME280 sensor replacement"},
    {"date": "2026-03-22", "event": "16V 20F cap bank replacement + ina219 0x41 replacement"},
    {"date": "2026-03-23", "event": "System on bench power supply 11.38V steady for troubleshooting"},
    {"date": "2026-03-24 18:00", "event": "Battery disconnected for service"},
    {"date": "2026-03-25 19:21", "event": "Battery reconnected + ESP8266 battery monitor added (cap bank removed), ina41 sensor disconnected"},
]

FLASK_SOLAR_URL = "http://192.168.1.100:5000/solarpi/timeseries"
FLASK_ESP8266_URL = "http://192.168.1.100:5000/esp8266"

# ====================== FETCH ======================
def fetch_flask_data(url, source_name):
    print(f"Fetching data from {source_name}...")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        df_new = pd.DataFrame(data)
        if 'timestamp' in df_new.columns:
            df_new['timestamp'] = pd.to_datetime(df_new['timestamp'], errors='coerce')
            df_new = df_new.dropna(subset=['timestamp']).set_index('timestamp')
        print(f"✅ Fetched {len(df_new)} records from {source_name}")
        return df_new
    except Exception as e:
        print(f"⚠️ Failed to fetch from {source_name}: {e}")
        return pd.DataFrame()

df_solar = fetch_flask_data(FLASK_SOLAR_URL, "SolarPi main")
df_esp = fetch_flask_data(FLASK_ESP8266_URL, "ESP8266 battery monitor")

print("\n💥 SolarPi columns:\n", df_solar.columns.tolist())
print("💥 ESP8266 columns:\n", df_esp.columns.tolist())

# Diagnostic for April 23 (optional)
test_day = "2026-04-23"
mask_test = (df_esp.index >= test_day) & (df_esp.index < pd.Timestamp(test_day) + pd.Timedelta(days=1))
if mask_test.any():
    vmax_test = df_esp.loc[mask_test, 'bus_voltage_v'].max()
    print(f"\n🔍 Diagnostic: On {test_day}, ESP8266 max voltage = {vmax_test:.3f} V")
    if vmax_test < 14.2:
        print("   ⚠️ WARNING: Max voltage below 14.2V – data may be aggregated or missing high‑resolution samples.")
    else:
        print("   ✓ High voltage detected – raw data seems correct.")
else:
    print(f"\n⚠️ No ESP8266 data for {test_day}")

# Unified temperature (SolarPi)
if 'bme_temp' in df_solar.columns:
    df_solar['temp'] = df_solar['bme_temp']
    print("✅ Unified temp: bme_temp only")
    print(f"• Temp (BME280): {df_solar['temp'].mean():.1f}°C avg (min {df_solar['temp'].min():.1f}°C) [{len(df_solar):,} samples]")

# ====================== ESP8266 COULOMB SOC ======================
df_esp['dt_h'] = df_esp.index.to_series().diff().dt.total_seconds().div(3600.0).fillna(0)
df_esp['soc_ah_delta'] = -df_esp['current_ma'] / 1000.0 * df_esp['dt_h']   # positive = charging
df_esp['soc_ah'] = df_esp['soc_ah_delta'].cumsum()

# ----- Robust anchoring: 1-min resample, 10-min rolling means -----
df_esp_min = df_esp[['bus_voltage_v', 'current_ma']].resample('1min').mean()
df_esp_min['v_avg'] = df_esp_min['bus_voltage_v'].rolling(window=10, min_periods=1).mean()
df_esp_min['i_avg'] = df_esp_min['current_ma'].rolling(window=10, min_periods=1).mean()

# Anchor condition: voltage >= 14.2V, net current between -200mA and +100mA, daytime 10am-4pm
df_esp_min['anchor_cond'] = (
    (df_esp_min['v_avg'] >= 14.2) &
    (df_esp_min['i_avg'] >= -200) & (df_esp_min['i_avg'] <= 100) &
    (df_esp_min.index.hour >= 10) & (df_esp_min.index.hour <= 16)
)
# Require 10 consecutive minutes
df_esp_min['sustained'] = df_esp_min['anchor_cond'].rolling(window=10, min_periods=10).sum() == 10
sustained_starts = df_esp_min[df_esp_min['sustained'] & (~df_esp_min['sustained'].shift(1).fillna(False))].index

# Mark days with at least one sustained anchor
anchor_days = pd.Series(False, index=pd.date_range(df_esp.index.min().normalize(), df_esp.index.max().normalize(), freq='D'))
if not sustained_starts.empty:
    for start in sustained_starts:
        anchor_days[start.normalize()] = True
    anchor_time = sustained_starts[0]
    print(f"🔋 First Coulomb anchor at {anchor_time} (≥14.2V, net current ≤200mA for 10 min)")
    anchor_idx = df_esp.index.get_indexer([anchor_time], method='nearest')[0]
    df_esp.loc[df_esp.index >= df_esp.index[anchor_idx], 'soc_ah'] = 0.0
    df_esp.loc[df_esp.index >= df_esp.index[anchor_idx], 'soc_ah'] = (
        df_esp.loc[df_esp.index >= df_esp.index[anchor_idx], 'soc_ah_delta'].cumsum()
    )
else:
    print("⚠️ No sustained full‑charge anchor found; SoC will drift.")
    anchor_days = pd.Series(False, index=pd.date_range(df_esp.index.min().normalize(), df_esp.index.max().normalize(), freq='D'))

df_esp['soc_pct_coulomb'] = (100.0 + df_esp['soc_ah'] / BATTERY_AH * 100.0).clip(0, 100).round(1)

# ====================== DAILY STATS: SOLARPI (BUCK EFFICIENCY + TEMP) ======================
def daily_solar_stats(group):
    if len(group) == 0:
        return pd.Series({
            'pi_wh': 0,
            'ina44_v_min': np.nan, 'ina44_v_max': np.nan,
            'ina44_i_min': np.nan, 'ina44_i_max': np.nan,
            'ina45_v_min': np.nan, 'ina45_v_max': np.nan,
            'ina45_i_min': np.nan, 'ina45_i_max': np.nan,
            'buck_eff_avg': np.nan, 'buck_eff_min': np.nan, 'buck_eff_max': np.nan,
            'temp_min': np.nan, 'temp_max': np.nan, 'temp_avg': np.nan
        })
    dt = group.index.to_series().diff().dt.total_seconds().fillna(0)
    v_in = group['ina44_v']; i_in = group['ina44_i']
    v_out = group['ina45_v']; i_out = group['ina45_i']

    # Pi energy
    pi_wh = (i_out * v_out / 1e6 * dt).sum()

    # Daily min/max for voltages and currents (same as before)
    valid_v_in = v_in[v_in.notna() & (v_in >= V_IGNORE_FOR_TRENDS)]
    ina44_v_min = valid_v_in.min() if not valid_v_in.empty else np.nan
    ina44_v_max = valid_v_in.max() if not valid_v_in.empty else np.nan
    valid_i_in = i_in[i_in.notna()]
    ina44_i_min = valid_i_in.min() if not valid_i_in.empty else np.nan
    ina44_i_max = valid_i_in.max() if not valid_i_in.empty else np.nan

    valid_v_out = v_out[v_out.notna()]
    ina45_v_min = valid_v_out.min() if not valid_v_out.empty else np.nan
    ina45_v_max = valid_v_out.max() if not valid_v_out.empty else np.nan
    valid_i_out = i_out[i_out.notna()]
    ina45_i_min = valid_i_out.min() if not valid_i_out.empty else np.nan
    ina45_i_max = valid_i_out.max() if not valid_i_out.empty else np.nan

    # Buck efficiency: average (using mean power) and min/max (using per-sample where input power > 0.1W)
    p_in = i_in * v_in
    p_out = i_out * v_out
    # Average efficiency (mean power ratio)
    p_in_avg = p_in.mean()
    p_out_avg = p_out.mean()
    buck_eff_avg = round((p_out_avg / p_in_avg) * 100, 1) if p_in_avg > 0 else np.nan

    # Min/max efficiency on valid samples (avoid near-zero input power)
    mask_valid = (p_in > 0.1) & (p_in.notna()) & (p_out.notna())
    if mask_valid.any():
        eff = (p_out[mask_valid] / p_in[mask_valid]) * 100
        buck_eff_min = round(eff.min(), 1)
        buck_eff_max = round(eff.max(), 1)
    else:
        buck_eff_min = buck_eff_max = np.nan

    # Temperature statistics
    if 'temp' in group.columns:
        temp_series = group['temp'].dropna()
        if not temp_series.empty:
            temp_min = round(temp_series.min(), 1)
            temp_max = round(temp_series.max(), 1)
            temp_avg = round(temp_series.mean(), 1)
        else:
            temp_min = temp_max = temp_avg = np.nan
    else:
        temp_min = temp_max = temp_avg = np.nan

    return pd.Series({
        'pi_wh': round(pi_wh, 2),
        'ina44_v_min': round(ina44_v_min,2), 'ina44_v_max': round(ina44_v_max,2),
        'ina44_i_min': round(ina44_i_min,2), 'ina44_i_max': round(ina44_i_max,2),
        'ina45_v_min': round(ina45_v_min,2), 'ina45_v_max': round(ina45_v_max,2),
        'ina45_i_min': round(ina45_i_min,2), 'ina45_i_max': round(ina45_i_max,2),
        'buck_eff_avg': buck_eff_avg, 'buck_eff_min': buck_eff_min, 'buck_eff_max': buck_eff_max,
        'temp_min': temp_min, 'temp_max': temp_max, 'temp_avg': temp_avg
    })

daily_solar = df_solar.groupby(pd.Grouper(freq='D')).apply(daily_solar_stats, include_groups=False)
if isinstance(daily_solar, pd.Series):
    daily_solar = daily_solar.to_frame().T

# ====================== DAILY STATS: ESP8266 (NET ENERGY, SOC, BUS VOLTAGE) ======================
def daily_esp_stats(group):
    if len(group) == 0:
        return pd.Series({'net_energy_wh':0, 'net_avg_ma':0, 'soc_coulomb':np.nan,
                          'bus_v_min':np.nan, 'bus_v_max':np.nan})
    dt = group.index.to_series().diff().dt.total_seconds().fillna(0)
    v_bus = group['bus_voltage_v']; i_bus = group['current_ma']
    net_energy_wh = (i_bus * v_bus / 1e6 * dt).sum()
    net_avg_ma = i_bus.mean() or 0
    if 'soc_pct_coulomb' in group.columns:
        last_soc = group['soc_pct_coulomb'].dropna()
        soc_coulomb = last_soc.iloc[-1] if not last_soc.empty else np.nan
    else:
        soc_coulomb = np.nan
    valid_v = v_bus[v_bus.notna() & (v_bus >= V_IGNORE_FOR_TRENDS)]
    bus_v_min = valid_v.min() if not valid_v.empty else np.nan
    bus_v_max = valid_v.max() if not valid_v.empty else np.nan
    return pd.Series({
        'net_energy_wh': round(net_energy_wh,2), 'net_avg_ma': round(net_avg_ma,2),
        'soc_coulomb': round(soc_coulomb,1) if pd.notna(soc_coulomb) else np.nan,
        'bus_v_min': round(bus_v_min,2), 'bus_v_max': round(bus_v_max,2)
    })

daily_esp = df_esp.groupby(pd.Grouper(freq='D')).apply(daily_esp_stats, include_groups=False)
if isinstance(daily_esp, pd.Series):
    daily_esp = daily_esp.to_frame().T

# Add anchor validity column to daily_esp
daily_esp['anchor_valid'] = daily_esp.index.map(lambda d: anchor_days.get(d, False))

# ====================== MERGE DAILY TABLES ======================
merged = daily_solar.join(daily_esp, how='outer')

# Select and rename columns as requested
merged = merged[['pi_wh', 'net_energy_wh', 'bus_v_min', 'bus_v_max',
                 'buck_eff_avg', 'buck_eff_min', 'buck_eff_max',
                 'soc_coulomb', 'ina45_v_min', 'ina45_v_max',
                 'ina45_i_min', 'ina45_i_max', 'temp_min', 'temp_max', 'temp_avg', 'anchor_valid']]

merged = merged.rename(columns={
    'pi_wh': 'PiWh',
    'net_energy_wh': 'NetWh',
    'bus_v_min': 'BatVmin',
    'bus_v_max': 'BatVmax',
    'buck_eff_avg': 'Buck%',
    'buck_eff_min': 'Buck_min%',
    'buck_eff_max': 'Buck_max%',
    'soc_coulomb': 'SoC%',
    'ina45_v_min': 'USB5V_Vmin',
    'ina45_v_max': 'USB5V_Vmax',
    'ina45_i_min': 'USB5V_Imin',
    'ina45_i_max': 'USB5V_Imax',
    'temp_min': 'BME_temp_min',
    'temp_max': 'BME_temp_max',
    'temp_avg': 'BME_temp_avg',
})

# ====================== TODAY'S HOURLY SNAPSHOT ======================
print("\n📊 TODAY'S HOURLY SNAPSHOT (Current 12V Battery Bus)")
today = pd.Timestamp.now().normalize()
today_esp = df_esp[df_esp.index >= today]
if not today_esp.empty:
    hourly = today_esp.resample('H').agg({'bus_voltage_v':'mean','current_ma':'mean'}).round(2)
    today_solar = df_solar[df_solar.index >= today]
    if not today_solar.empty:
        solar_hourly = today_solar.resample('H').agg({'ina45_v':'mean','ina45_i':'mean'}).round(2)
        hourly['Pi_Wh'] = (solar_hourly['ina45_i'] * solar_hourly['ina45_v'] / 1e3).fillna(0)
        hourly['Net_mA'] = hourly['current_ma']
        hourly['Bat_V'] = hourly['bus_voltage_v']
        print(hourly[['Pi_Wh','Bat_V','Net_mA']].to_string())
    else:
        print("No SolarPi data for today.")
else:
    print("No ESP8266 data for today.")

# ====================== DASHBOARD ======================
print("\n" + "="*80)
print("     ADVANCED SOLARPI DASHBOARD: 40W UPGRADE ACTIVE (ESP8266 integrated)")
print("="*80)
print("QUICK STATS (from ESP8266, after 2026-03-25):")
total_net = merged['NetWh'].sum()
total_pi = merged['PiWh'].sum()
print(f"• Total Net Battery Energy: {total_net:.0f} Wh")
print(f"• Total Pi Consumption: {total_pi:.0f} Wh")
print(f"• Solar Status: {'✅ ACTIVE' if merged['NetWh'].iloc[-1] > 0 else '⚠️ NO INPUT'}")
crit_days = (merged['BatVmin'] < V_CRITICAL).sum()
print(f"• Critical Days (bus V < {V_CRITICAL}V): {crit_days} (service days suppressed)\n")
print("🔋 CAPACITOR BANK HEALTH: N/A - Cap bank intentionally removed after 2026-03-22")

# ====================== RECENT PERFORMANCE TABLE ======================
recent = merged.tail(25).copy().round(2)

# Format Buck columns (they already contain numbers, but we want consistent width)
def fmt_buck(x):
    if pd.isna(x):
        return '   --'
    return f"{x:5.1f}"
recent['Buck%'] = recent['Buck%'].apply(fmt_buck)
recent['Buck_min%'] = recent['Buck_min%'].apply(fmt_buck)
recent['Buck_max%'] = recent['Buck_max%'].apply(fmt_buck)

# Add anchor flag (asterisk for days without valid anchor)
recent['Anchor'] = recent['anchor_valid'].map({True: ' ', False: '*'})

# Optional trend arrows for battery voltage and SoC
def add_trend(df, col, th=0.02):
    prev = df[col].shift(1)
    diff = df[col] - prev
    return ['▲' if d>th else '▼' if d<-th else '→' if not pd.isna(d) else '' for d in diff]
recent['Bat_tr'] = add_trend(recent, 'BatVmin', 0.02)
recent['SoC_tr'] = add_trend(recent, 'SoC%', 0.5)

print("\nRECENT PERFORMANCE (Last 25 Days):")
print(f"{'Date':<12} {'PiWh':>6} {'NetWh':>6} {'BatVmin':>7} {'BatVmax':>7} "
      f"{'Buck%':>6} {'Buck_min':>8} {'Buck_max':>8} {'SoC%':>5} "
      f"{'USB5V_Vmin':>9} {'USB5V_Vmax':>9} {'USB5V_Imin':>9} {'USB5V_Imax':>9} "
      f"{'Tmin':>6} {'Tmax':>6} {'Tavg':>6}")
print('-'*130)

for idx, row in recent.iterrows():
    # Use the correct column names (as renamed)
    soc_str = f"{row['SoC%']:>5.1f}{row['Anchor']}"   # Note: 'SoC%' not 'SoC_%'
    print(f"{idx.strftime('%Y-%m-%d'):<12} {row['PiWh']:>6.1f} {row['NetWh']:>6.1f} "
          f"{row['BatVmin']:>7.2f} {row['BatVmax']:>7.2f} "
          f"{row['Buck%']:>6} {row['Buck_min%']:>8} {row['Buck_max%']:>8} {soc_str:>6} "
          f"{row['USB5V_Vmin']:>9.2f} {row['USB5V_Vmax']:>9.2f} "
          f"{row['USB5V_Imin']:>9.1f} {row['USB5V_Imax']:>9.1f} "
          f"{row['BME_temp_min']:>6.1f} {row['BME_temp_max']:>6.1f} {row['BME_temp_avg']:>6.1f}")

print("\n* Buck% = average efficiency (power‑mean). Buck_min% / Buck_max% = daily min/max instantaneous efficiency (input power >0.1W).")
print("* SoC% from ESP8266 Coulomb counting, anchored during sustained 14.2V, low net current. Asterisk (*) means no anchor that day.")
print("* NetWh from ESP8266 (battery net energy).")
print("* BME temperatures in °C.")

# ====================== MAINTENANCE & MILESTONES ======================
print("\n🔧 MAINTENANCE / ENGINEERING EVENTS:")
for ev in MAINTENANCE_EVENTS:
    print(f"• {ev['date']}: {ev['event']}")
print("\n📅 HARDWARE MILESTONES:")
print("• 2025-10-23: 5Ah LiPo\n• 2025-12-06: 20Ah LiPo\n• 2026-02-04 18:33: 40W Solar Upgrade")
print("• 2026-03-09 19:48: HDC1000 → BME280\n• 2026-03-22 20:03: 16V 20F cap bank replacement")
print("• 2026-03-22 20:03: ina219 0x41 replacement")

# ====================== TODAY'S SUMMARY ======================
print(f"\n🔋 TODAY: {merged['NetWh'].iloc[-1]:.1f}Wh net energy")
if 'soc_pct_coulomb' in df_esp:
    print(f"🔋 Last Coulomb SoC: {df_esp['soc_pct_coulomb'].iloc[-1]:.1f}% (from ESP8266)")