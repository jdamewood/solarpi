import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.interpolate import griddata
import requests
from requests.exceptions import RequestException

# ====================== CONFIGURATION ======================
FLASK_SOLAR_URL = "http://192.168.1.100:5000/solarpi/timeseries"

# Order of sensors (2x4 grid, left to right, top to bottom)
plot_cols_dict = {
    'cpu_temp': 'CPU Temperature (°C)',
    'bme_temp': 'BME Temperature (°C)',
    'bme_hum': 'BME Humidity (%)',
    'ina44_v': 'Bulk Input Voltage (V)',
    'tsl39_ch1': 'TSL39 CH1',
    'tsl39_ch0': 'TSL39 CH0',
    'tsl29_ch1': 'TSL29 CH1',
    'tsl29_ch0': 'TSL29 CH0'
}

# ====================== FETCH DATA ======================
try:
    print(f"Fetching data from {FLASK_SOLAR_URL} ...")
    response = requests.get(FLASK_SOLAR_URL, timeout=60)
    response.raise_for_status()
    data = response.json()
    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp').sort_index().reset_index()
    print(f"✅ Loaded {len(df)} records")
except RequestException as e:
    print(f"❌ Failed to fetch data: {e}")
    exit(1)

# ====================== PREPROCESSING ======================
df["hour_of_day"] = df["timestamp"].dt.hour + df["timestamp"].dt.minute / 60.0
df["day_index"] = df["timestamp"].dt.dayofyear

# Keep only columns that exist in the DataFrame
available_cols = [col for col in plot_cols_dict.keys() if col in df.columns]
plot_cols = available_cols
print(f"Available columns for waterfall plots: {plot_cols}")

if not plot_cols:
    print("No matching columns found. Available columns:", df.columns.tolist())
    exit(1)

# ====================== CREATE WATERFALL PLOTS ======================
fig = plt.figure(figsize=(20, 12))
fig.suptitle("SolarPi 3D Waterfall Analysis", fontsize=20, fontweight='bold', y=0.98)

# Grid parameters (adjust as needed)
x_bins = np.arange(0, 24, 0.5)  # hourly bins (0.5 hour resolution)
y_bins = np.arange(df['day_index'].min(), df['day_index'].max() + 1, 1)

for i, col in enumerate(plot_cols):
    ax = fig.add_subplot(2, 4, i + 1, projection='3d')
    data_sub = df[['hour_of_day', 'day_index', col]].dropna()

    if data_sub.empty:
        ax.text(0.5, 0.5, f"No {col} data", ha='center', va='center', transform=ax.transAxes)
        ax.set_title(plot_cols_dict[col], fontweight='bold', fontsize=12)
        continue

    # Normalize TSL light channels to [0,1] for better visualisation
    if 'tsl' in col:
        vals = data_sub[col].values
        clip_max = np.percentile(vals, 90)  # avoid extreme outliers
        vals = np.clip(vals, 0, clip_max)
        if np.ptp(vals) > 0:
            vals = (vals - vals.min()) / (vals.max() - vals.min())
        else:
            vals = np.zeros_like(vals)
        z_label = f"{plot_cols_dict[col]} (norm 0-1)"
    else:
        vals = data_sub[col].values
        z_label = plot_cols_dict[col]

    # Interpolate onto regular grid
    X, Y = np.meshgrid(x_bins, y_bins)
    points = data_sub[['hour_of_day', 'day_index']].values
    try:
        Z = griddata(points, vals, (X, Y), method='linear')
    except Exception as e:
        print(f"Interpolation error for {col}: {e}")
        Z = np.full_like(X, np.nan)

    # Fill holes with nearest neighbour
    if np.any(np.isnan(Z)):
        Z = griddata(points, vals, (X, Y), method='nearest')

    # Create surface
    surf = ax.plot_surface(X, Y, Z, cmap='viridis', linewidth=0, antialiased=True)
    ax.set_title(plot_cols_dict[col], fontweight='bold', fontsize=12)
    ax.set_xlabel("Hour of Day")
    if i < 4:
        ax.set_ylabel("Day of Year")
    ax.set_zlabel(z_label)

    # Colorbar
    fig.colorbar(surf, ax=ax, shrink=0.7, label=z_label)

plt.tight_layout()
plt.show()