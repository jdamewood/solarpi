import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import norm
import numpy as np
import requests
from requests.exceptions import RequestException

FLASK_SOLAR_URL = "http://192.168.1.100:5000/solarpi/timeseries"

# ====================== FETCH DATA ======================
try:
    print(f"Fetching data from {FLASK_SOLAR_URL} ...")
    response = requests.get(FLASK_SOLAR_URL, timeout=30)
    response.raise_for_status()
    data = response.json()
    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    print(f"✅ Loaded {len(df)} clean rows")
except RequestException as e:
    print(f"❌ Failed to fetch data: {e}")
    exit(1)

print("Available columns:", df.columns.tolist())

# Only use columns that exist (the JSON may have slightly different names)
sensor_columns = []
current_columns = ['ina45_i', 'ina41_i', 'ina44_i']
for col in ["ina45_v", "ina45_i", "ina41_v", "ina41_i", "ina44_v", "ina44_i",
            "tsl39_ch0", "tsl39_ch1", "tsl29_ch0", "tsl29_ch1",
            "bme_temp", "cpu_temp", "bme_hum", "wifi_rssi"]:
    if col in df.columns:
        sensor_columns.append(col)
    else:
        print(f"⚠️ Missing: {col}")

print(f"\n📊 Analyzing {len(sensor_columns)} available columns")

# *** SUMMARY TABLE (SAFE) ***
print("\n📊 SENSOR DATA SUMMARY")
summary_data = []
for col in sensor_columns:
    count = df[col].count()
    if count > 0:
        summary_data.append({
            'Column': col,
            'Count': count,
            'Mean': df[col].mean(),
            'Min': df[col].min(),
            'Max': df[col].max(),
            'Range': f"{df[col].min():.1f}-{df[col].max():.1f}"
        })

summary = pd.DataFrame(summary_data)
print(summary.round(3).to_string(index=False))

# BATTERY DISCHARGE + SOLAR TAIL ANALYSIS
high_tail = df[df['ina41_v'] > 13.0]

print("\nHIGH VOLTAGE TAIL (>13V) CONTEXT:")
print(f"Solar current: {high_tail['ina41_i'].mean():.0f} mA")   # already in mA
print(f"Battery current: {high_tail['ina45_i'].mean():.0f} mA")
print(f"BME temp: {high_tail['bme_temp'].mean():.1f}°C")
print(f"Lux: {high_tail['tsl39_lux'].mean():.0f} lux")
print(f"Rows: {len(high_tail)}/{len(df)} ({100*len(high_tail)/len(df):.1f}%)")

# *** PLOTTING LOOP ***
for col in sensor_columns:
    data = df[col].dropna()
    if len(data) < 20: continue

    # For current columns, they are already in mA – no scaling needed
    if col in current_columns:
        data_plot = data
        unit = "mA"
    else:
        data_plot = data
        unit = ""

    print(f"\n🔍 {col}: n={len(data_plot)}, range={data_plot.min():.1f}-{data_plot.max():.1f}{unit}")

    # IQR cleaning
    Q1, Q3 = data_plot.quantile([0.25, 0.75])
    IQR = Q3 - Q1
    data_clean = data_plot[(data_plot >= Q1 - 1.5 * IQR) & (data_plot <= Q3 + 1.5 * IQR)]

    print(f"   Cleaned: n={len(data_clean)} ({100 * len(data_clean) / len(data_plot):.0f}%)")

    if len(data_clean) < 30: continue

    plt.figure(figsize=(12, 6))
    plt.hist(data_clean, bins=min(50, len(data_clean) // 10), density=True, alpha=0.7, color='skyblue')
    mean, sigma = data_clean.mean(), data_clean.std()
    x = np.linspace(data_clean.min(), data_clean.max(), 100)
    plt.plot(x, norm.pdf(x, mean, sigma), 'r-', linewidth=3)
    plt.axvline(mean, color='orange', linewidth=2, label=f'Mean: {mean:.1f}{unit}')
    plt.title(f'{col}: {mean:.1f}±{sigma:.1f} {unit}')
    plt.xlabel(f'{col} ({unit})')
    plt.ylabel('Density')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()

print("\n✅ Analysis complete. Data source: Flask JSON.")