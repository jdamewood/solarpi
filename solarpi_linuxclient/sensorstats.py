# version 2.0 - Fetch data from Flask endpoint instead of CSV
# All currents are assumed to be in mA (as delivered by the JSON endpoint)

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import warnings
import requests
from requests.exceptions import RequestException

warnings.filterwarnings("ignore")

FLASK_SOLAR_URL = "http://192.168.1.100:5000/solarpi/timeseries"
SAMPLE_INTERVAL_SEC = 42
UPGRADE_TIME = pd.to_datetime('2026-02-04 18:33:00')
BME280_CUTOVER = pd.to_datetime('2026-03-09 19:48:57')
BATTERY_AH = 20.0
CHARGER_EFFICIENCY = 0.82
V_WARN = 10.5
V_CRITICAL = 9.3

# ====================== FETCH DATA FROM FLASK ======================
try:
    print(f"Fetching data from {FLASK_SOLAR_URL} ...")
    response = requests.get(FLASK_SOLAR_URL, timeout=30)
    response.raise_for_status()
    data = response.json()
    # Assume data is a list of dictionaries (one per sample)
    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp')
    print(f"✅ Loaded {len(df):,} samples from Flask endpoint")
except RequestException as e:
    print(f"❌ Failed to fetch data: {e}")
    exit(1)

# NOTE: The JSON already contains currents in mA – do NOT multiply by 1000
# If your endpoint returns Amperes, remove the comment below:
# df['ina44_i'] = df['ina44_i'] * 1000
# df['ina45_i'] = df['ina45_i'] * 1000

# Clean unrealistic values
df['ina44_v'] = df['ina44_v'].where((df['ina44_v'] >= 9.0) & (df['ina44_v'] <= 14.9), np.nan)
df['ina44_i'] = df['ina44_i'].clip(-5000, 5000)
df['ina45_i'] = df['ina45_i'].clip(-100, 5000)

# Unified temperature column
if 'bme_temp' in df.columns and 'hdc_temp' in df.columns:
    df['temp'] = np.where(df.index >= BME280_CUTOVER, df['bme_temp'], df['hdc_temp'])
elif 'bme_temp' in df.columns:
    df['temp'] = df['bme_temp']
else:
    df['temp'] = df.get('hdc_temp', 20.0)

print(f"• Average load current: {df['ina44_i'].mean():.1f} mA")

# ====================== HELPER FUNCTIONS (unchanged) ======================
def filtered_vmax(v_series):
    v = v_series.dropna()
    if v.empty:
        return np.nan
    v = v[(v >= 9.0) & (v <= 14.9)]
    if v.empty:
        return np.nan
    return v.max()

def get_temp_corr(t):
    temp_correction = {(0,10):1.05, (10,20):1.02, (20,25):1.00, (25,35):0.99, (35,45):0.97}
    for (lo, hi), factor in sorted(temp_correction.items()):
        if lo <= t < hi:
            return factor
    return 1.0

def voltage_to_soc(v, temp=np.nan):
    if pd.isna(v) or v < 10.0:
        return np.nan
    corr = get_temp_corr(temp) if not pd.isna(temp) else 1.0
    v_corr = v * corr
    ocv_v = [10.0,11.8,12.0,12.1,12.2,12.3,12.4,12.5,12.6,12.8,13.0,13.2,13.6,13.8]
    ocv_s = [0,5,10,20,30,40,50,60,70,80,90,95,99,100]
    return float(np.interp(v_corr, ocv_v, ocv_s))

# ====================== DAILY STATS ======================
def daily_stats_func(group):
    if len(group) < 2:
        return pd.Series({
            'energy_wh': 0.0, 'solar_wh': 0.0, 'min_v': np.nan, 'max_v': np.nan,
            'start_v': np.nan, 'end_v': np.nan, 'Risk': 'EMPTY', 'avg_temp': np.nan,
            'C_Rate': 0.0, 'Load_Avg_mA': 0.0, 'Solar_Avg_mA': 0.0,
            'Net_Avg_mA': 0.0, 'Efficiency_%': np.nan
        })

    dt = group.index.to_series().diff().dt.total_seconds()
    dt = dt.fillna(SAMPLE_INTERVAL_SEC)
    dt = dt.replace(0, SAMPLE_INTERVAL_SEC)

    energy_wh = (group['ina44_i'] * group['ina44_v'] / 1_000_000 * dt).sum()
    solar_wh  = (group['ina45_i'] * group.get('ina45_v', group['ina44_v']) / 1_000_000 * dt).sum()

    load_avg_ma  = group['ina44_i'].mean()
    solar_avg_ma = group['ina45_i'].mean()
    net_avg_ma   = group['ina44_i'].mean() - group.get('ina41_i', 0).mean()

    v_min   = group['ina44_v'].min()
    v_max   = filtered_vmax(group['ina44_v'])
    v_start = group['ina44_v'].iloc[0]
    v_end   = group['ina44_v'].iloc[-1]

    risk = 'CRITICAL' if (group['ina44_v'] < V_CRITICAL).mean() > 0.05 else 'GOOD'

    pwr_in  = (group['ina44_v'] * group['ina44_i']).mean()
    pwr_out = (group.get('ina45_v', group['ina44_v']) * group['ina45_i']).mean()
    eff = round((pwr_out / pwr_in) * 100, 1) if pwr_in > 5 else np.nan

    avg_temp = group['temp'].mean() if 'temp' in group.columns else np.nan

    return pd.Series({
        'energy_wh':    round(energy_wh, 2),
        'solar_wh':     round(solar_wh, 2),
        'min_v':        round(v_min, 2),
        'max_v':        round(v_max, 2),
        'start_v':      round(v_start, 2),
        'end_v':        round(v_end, 2),
        'Risk':         risk,
        'avg_temp':     round(avg_temp, 2) if not pd.isna(avg_temp) else np.nan,
        'C_Rate':       round(net_avg_ma / 1000 / BATTERY_AH, 5),
        'Load_Avg_mA':  round(load_avg_ma, 2),
        'Solar_Avg_mA': round(solar_avg_ma, 2),
        'Net_Avg_mA':   round(net_avg_ma, 2),
        'Efficiency_%': eff,
    })

energy_df = df.groupby(pd.Grouper(freq='D')).apply(daily_stats_func)

# ====================== POST-PROCESSING ======================
energy_df['solar_wh_corrected'] = energy_df['solar_wh'] / CHARGER_EFFICIENCY
energy_df['Net_Daily_Wh'] = energy_df['solar_wh_corrected'] - energy_df['energy_wh']
energy_df['delta_v'] = energy_df['end_v'] - energy_df['start_v']
energy_df['Net_7d_Wh'] = energy_df['Net_Daily_Wh'].rolling(7, min_periods=1).mean()

# SoC calculation with float boost
energy_df['SoC_voltage'] = energy_df.apply(lambda r: voltage_to_soc(r['max_v'], r['avg_temp']), axis=1)
soc_clean = energy_df['SoC_voltage'].ffill()
energy_df['SoC (%)'] = soc_clean.rolling(3, min_periods=1).median().round(1)
energy_df.loc[energy_df['max_v'] >= 13.3, 'SoC (%)'] = 100.0   # Force 100% in float

# Hourly data for plots
hourly = df.resample('H').agg({'ina44_v': 'mean', 'ina44_i': 'mean', 'ina45_i': 'mean'})

# ====================== DASHBOARD ======================
print("\n" + "="*90)
print("     SOLARPI DASHBOARD v2.0 – Flask Data Source")
print("="*90)

print(f"• Total samples     : {len(df):,}")
print(f"• Average load      : {df['ina44_i'].mean():.1f} mA  ({df['ina44_i'].mean() * 13.15 / 1000:.2f} W)")
print(f"• SoC today         : {energy_df['SoC (%)'].iloc[-1]:.1f}%")
print(f"• Avg daily ΔV      : {energy_df['delta_v'].mean():+.3f} V")
print(f"• Net 7-day (calc)  : {energy_df['Net_7d_Wh'].iloc[-1]:+.1f} Wh/day")

print("\nRECENT 10 DAYS:")
cols = ['energy_wh', 'solar_wh', 'min_v', 'max_v', 'delta_v', 'SoC (%)',
        'Net_Daily_Wh', 'Efficiency_%', 'Risk']
print(energy_df[cols].tail(10).round(2))

print("\nSYSTEM INTERPRETATION:")
if energy_df['delta_v'].mean() > -0.05:
    print("   ✅ Battery reaches full charge / float almost every day.")
    print("      Small overnight voltage drop only. System is balanced in practice.")
    print("      Negative Wh net is mainly due to solar curtailment when battery is full.")
else:
    print("   ⚠️  Voltage trending downward — monitor solar input vs load.")

print("\n" + "="*90)

# ====================== PLOTS (unchanged) ======================
fig, axs = plt.subplots(2, 2, figsize=(15, 11))

# Plot 1: Daily Energy Balance
axs[0,0].bar(energy_df.index, energy_df['solar_wh'], color='orange', alpha=0.7, label='Solar')
axs[0,0].bar(energy_df.index, -energy_df['energy_wh'], color='steelblue', alpha=0.7, label='Load')
axs[0,0].axvline(UPGRADE_TIME, color='green', linestyle='--', label='40W Upgrade')
axs[0,0].set_title('Daily Energy Balance')
axs[0,0].set_ylabel('Wh')
axs[0,0].legend()
axs[0,0].tick_params(axis='x', rotation=45)
axs[0,0].grid(True, alpha=0.3)

# Plot 2: SoC and Delta V
axs[0,1].plot(energy_df.index, energy_df['SoC (%)'], 'go-', label='SoC % (OCV)')
axs[0,1].set_ylabel('SoC %')
axs[0,1].set_ylim(0, 105)
ax2b = axs[0,1].twinx()
ax2b.plot(energy_df.index, energy_df['delta_v'], 'b--', label='Daily ΔV')
ax2b.set_ylabel('ΔV (Volts)')
axs[0,1].set_title('SoC and Daily Voltage Change')
axs[0,1].legend(loc='upper left')
ax2b.legend(loc='upper right')
axs[0,1].tick_params(axis='x', rotation=45)
axs[0,1].grid(True, alpha=0.3)

# Plot 3: Voltage Over Time
axs[1,0].plot(hourly.index, hourly['ina44_v'], color='steelblue', label='Hourly Voltage')
axs[1,0].axhline(V_WARN, color='orange', linestyle=':', label=f'Warning ({V_WARN}V)')
axs[1,0].axhline(V_CRITICAL, color='red', linestyle='--', label=f'Brownout ({V_CRITICAL}V)')
axs[1,0].set_title('Battery Voltage')
axs[1,0].set_ylabel('Voltage (V)')
axs[1,0].legend()
axs[1,0].tick_params(axis='x', rotation=45)
axs[1,0].grid(True, alpha=0.3)

# Plot 4: Solar vs Load colored by ΔV
sc = axs[1,1].scatter(energy_df['energy_wh'], energy_df['solar_wh'],
                      c=energy_df['delta_v'], cmap='RdYlGn', alpha=0.7)
axs[1,1].set_xlabel('Load Energy (Wh)')
axs[1,1].set_ylabel('Solar Energy (Wh)')
axs[1,1].set_title('Solar vs Load (colored by daily ΔV)')
plt.colorbar(sc, ax=axs[1,1], label='ΔV (V)')

plt.tight_layout()
plt.show()

print("\n✅ Dashboard v2.0 complete. Data source: Flask -> JSON.")