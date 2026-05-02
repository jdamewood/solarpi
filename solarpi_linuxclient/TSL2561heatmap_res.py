import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import requests
from requests.exceptions import RequestException

FLASK_SOLAR_URL = "http://192.168.1.100:5000/solarpi/timeseries"

# ====================== FETCH DATA ======================
try:
    print(f"Fetching data from {FLASK_SOLAR_URL} ...")
    response = requests.get(FLASK_SOLAR_URL, timeout=60)
    response.raise_for_status()
    data = response.json()
    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp').sort_index()
    print(f"✅ Loaded {len(df)} records")
except RequestException as e:
    print(f"❌ Failed to fetch data: {e}")
    exit(1)

# --- Define expected sensor columns (adopt the actual names from JSON) ---
sensor_columns = [
    "ina45_v", "ina45_i", "ina41_v", "ina41_i", "ina44_v", "ina44_i",
    "tsl39_ch0", "tsl39_ch1", "tsl29_ch0", "tsl29_ch1",
    "tsl39_lux", "tsl29_lux",
    "bme_temp", "bme_hum", "cpu_temp", "wifi_rssi"
]

# Keep only columns that actually exist in the fetched DataFrame
existing_sensor_columns = [col for col in sensor_columns if col in df.columns]
missing = set(sensor_columns) - set(existing_sensor_columns)
if missing:
    print(f"⚠️ Missing columns (will be ignored): {missing}")

if not existing_sensor_columns:
    print("❌ No sensor columns found. Available columns:")
    print(df.columns.tolist())
    exit(1)

print(f"Analyzing {len(existing_sensor_columns)} sensor columns\n")

# --- Constant Frequency for Time Binning ---
FREQ = '30s'  # 30 second bins

def create_heatmap_data_fine(dataframe, value_column, freq=FREQ):
    dataframe['time_bin'] = dataframe.index.floor(freq).strftime('%H:%M:%S')
    pivot_table = dataframe.groupby([dataframe.index.date, dataframe['time_bin']])[value_column].mean().unstack()
    all_time_bins = pd.date_range('00:00:00', '23:59:59', freq=freq).strftime('%H:%M:%S')
    pivot_table = pivot_table.reindex(columns=all_time_bins)
    return pivot_table

def rms(x):
    return np.sqrt(np.mean(np.square(x)))

# --- Calculate statistics for existing columns ---
stats = df[existing_sensor_columns].agg(['mean', 'std', 'var', 'min', 'max']).T
stats.rename(columns={'std': 'sigma', 'var': 'variance'}, inplace=True)
stats['rms'] = df[existing_sensor_columns].apply(rms, axis=0)
stats['ucl'] = stats['mean'] + 3*stats['sigma']
stats['lcl'] = stats['mean'] - 3*stats['sigma']

# --- Time-series plots (7 subplots) ---
fig, axes = plt.subplots(7, 1, figsize=(16, 28), sharex=True)

def plot_sensor(ax, col, color=None, label=None):
    s = stats.loc[col]
    ax.plot(df.index, df[col], label=label or col, color=color)
    ax.axhline(s['mean'], color='g', linestyle='--', label=f"Mean={s['mean']:.2f}")
    ax.axhline(s['ucl'], color='r', linestyle=':', label=f"UCL={s['ucl']:.2f}")
    ax.axhline(s['lcl'], color='r', linestyle=':', label=f"LCL={s['lcl']:.2f}")
    ax.axhline(s['rms'], color='purple', linestyle='-.', label=f"RMS={s['rms']:.2f}")
    ax.set_ylabel(col)
    ax.legend(loc='upper right', fontsize='small')

# Plot voltages
for col in ["ina45_v", "ina41_v", "ina44_v"]:
    if col in existing_sensor_columns:
        plot_sensor(axes[0], col)
axes[0].set_title("INA219 Voltages")

# Plot currents
for col in ["ina45_i", "ina41_i", "ina44_i"]:
    if col in existing_sensor_columns:
        plot_sensor(axes[1], col)
axes[1].set_title("INA219 Currents")

# TSL2561 0x39 channels
for col in ["tsl39_ch0", "tsl39_ch1"]:
    if col in existing_sensor_columns:
        plot_sensor(axes[2], col)
axes[2].set_title("TSL2561 0x39 Channels")

# TSL2561 0x29 channels
for col in ["tsl29_ch0", "tsl29_ch1"]:
    if col in existing_sensor_columns:
        plot_sensor(axes[3], col)
axes[3].set_title("TSL2561 0x29 Channels")

# BME280 temperature
if "bme_temp" in existing_sensor_columns:
    plot_sensor(axes[4], "bme_temp", color='r')
    axes[4].set_title("BME280 Temperature")
else:
    axes[4].text(0.5, 0.5, "BME280 temperature data missing", ha='center', va='center')
    axes[4].axis('off')

# BME280 humidity
if "bme_hum" in existing_sensor_columns:
    plot_sensor(axes[5], "bme_hum", color='b')
    axes[5].set_title("BME280 Humidity")
else:
    axes[5].text(0.5, 0.5, "BME280 humidity data missing", ha='center', va='center')
    axes[5].axis('off')

# CPU temp and WiFi RSSI (twinx)
ax_cpu = axes[6]
ax_rssi = ax_cpu.twinx()
if "cpu_temp" in existing_sensor_columns:
    plot_sensor(ax_cpu, "cpu_temp", color='orange')
    ax_cpu.set_ylabel("CPU Temp (°C)", color='orange')
else:
    ax_cpu.text(0.5, 0.5, "CPU temp missing", ha='center', va='center', transform=ax_cpu.transAxes)
if "wifi_rssi" in existing_sensor_columns:
    plot_sensor(ax_rssi, "wifi_rssi", color='green')
    ax_rssi.set_ylabel("WiFi RSSI (dBm)", color='green')
else:
    ax_rssi.text(0.5, 0.5, "WiFi RSSI missing", ha='center', va='center', transform=ax_rssi.transAxes)
ax_cpu.tick_params(axis='y', labelcolor='orange')
ax_rssi.tick_params(axis='y', labelcolor='green')
ax_cpu.set_title("SOC Temp and WiFi RSSI")

axes[-1].set_xlabel("Timestamp")
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("Figure_4.png", dpi=150)
plt.close(fig)

# --- Heatmaps for lux (if TSL lux columns exist) ---
if "tsl39_lux" in existing_sensor_columns or "tsl29_lux" in existing_sensor_columns:
    # Larger figure, higher DPI helps remove pixel gaps
    fig_heatmaps, axes_heatmaps = plt.subplots(2, 1, figsize=(18, 14), dpi=120, sharex=True)


    # Helper to set ticks safely
    def set_time_ticks(ax, heatmap_data):
        if heatmap_data is None or heatmap_data.empty:
            return
        tick_interval_hours = 3
        n_bins = 3600 // 30  # 120 bins per hour? Actually 30s per bin -> 120 bins per hour
        step = tick_interval_hours * (3600 // 30)
        if step > 0:
            tick_positions = np.arange(0, len(heatmap_data.columns), step)
            tick_labels = [heatmap_data.columns[int(p)] for p in tick_positions if p < len(heatmap_data.columns)]
            ax.set_xticks(tick_positions[:len(tick_labels)])
            ax.set_xticklabels(tick_labels, rotation=45, ha='right')
        # Y-axis tick labels (dates)
        y_labels = [str(date) for date in heatmap_data.index]
        ax.set_yticks(np.arange(len(y_labels)))
        ax.set_yticklabels(y_labels)


    # TSL39 lux heatmap
    if "tsl39_lux" in existing_sensor_columns:
        df_heatmap_39 = df.copy()
        heatmap_data_39 = create_heatmap_data_fine(df_heatmap_39, 'tsl39_lux', freq=FREQ)
        # Fill NaN with 0 to avoid artifacts
        heatmap_data_39 = heatmap_data_39.fillna(0)
        im_39 = axes_heatmaps[0].imshow(
            heatmap_data_39,
            cmap='viridis',
            aspect='auto',
            interpolation='bilinear',  # ← fixes white gaps
            origin='lower',
            vmin=0,
            vmax=1000
        )
        axes_heatmaps[0].set_title('TSL2561 0x39 Lux - Light Intensity Heatmap (30s Bins)')
        axes_heatmaps[0].set_ylabel('Date')
        set_time_ticks(axes_heatmaps[0], heatmap_data_39)
        fig_heatmaps.colorbar(im_39, ax=axes_heatmaps[0], label='Lux (tsl39_lux)')
    else:
        axes_heatmaps[0].text(0.5, 0.5, "tsl39_lux data missing", ha='center', va='center')
        axes_heatmaps[0].set_title("TSL2561 0x39 Lux - No Data")

    # TSL29 lux heatmap
    if "tsl29_lux" in existing_sensor_columns:
        df_heatmap_29 = df.copy()
        heatmap_data_29 = create_heatmap_data_fine(df_heatmap_29, 'tsl29_lux', freq=FREQ)
        heatmap_data_29 = heatmap_data_29.fillna(0)
        im_29 = axes_heatmaps[1].imshow(
            heatmap_data_29,
            cmap='viridis',
            aspect='auto',
            interpolation='bilinear',
            origin='lower',
            vmin=0,
            vmax=1000
        )
        axes_heatmaps[1].set_title('TSL2561 0x29 Lux - Light Intensity Heatmap (30s Bins)')
        axes_heatmaps[1].set_xlabel('Hour of Day (24-hour period)')
        axes_heatmaps[1].set_ylabel('Date')
        set_time_ticks(axes_heatmaps[1], heatmap_data_29)
        fig_heatmaps.colorbar(im_29, ax=axes_heatmaps[1], label='Lux (tsl29_lux)')
    else:
        axes_heatmaps[1].text(0.5, 0.5, "tsl29_lux data missing", ha='center', va='center')
        axes_heatmaps[1].set_title("TSL2561 0x29 Lux - No Data")

    plt.tight_layout()
    plt.savefig("Figure_heatmaps.png", dpi=300, bbox_inches='tight')
    plt.show()
else:
    print("No TSL lux columns found; skipping heatmaps.")