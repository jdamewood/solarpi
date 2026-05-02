import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde
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

print("This program may take about 30 minutes to render plot")
print("Available columns:", df.columns.tolist())

# ====== EASY‑SWAP CONFIG BLOCK ======
# Change these two lines to pick which variables to plot in the heatmap
Y_VAR = "bme_temp"     # x‑axis (left/right)
X_VAR = "cpu_temp"     # y‑axis (up/down)
# Examples:
#   X_VAR = "tsl39_lux"; Y_VAR = "bme_temp"
#   X_VAR = "tsl39_lux"; Y_VAR = "cpu_temp"
#   X_VAR = "ina45_v";   Y_VAR = "tsl39_lux"
# ====================================

plt.style.use("dark_background")
fig, (ax1, ax2) = plt.subplots(
    2, 1, figsize=(14, 12),
    gridspec_kw={"height_ratios": [3, 1]}
)

# === HEATMAP: X_VAR vs Y_VAR ===
valid_data = df[[X_VAR, Y_VAR]].dropna()

# 1. CYAN ORBITS (24hr cycles)
for hour in range(24):
    hour_data = valid_data[valid_data.index.hour == hour]
    if len(hour_data) > 10:
        ax1.plot(hour_data[X_VAR], hour_data[Y_VAR],
                 alpha=0.15, lw=1.2, color="cyan")

# 2. PLASMA DENSITY CLOUD
xy = np.vstack([valid_data[X_VAR], valid_data[Y_VAR]])
z = gaussian_kde(xy)(xy)
scatter = ax1.scatter(xy[0], xy[1], c=z, s=12, cmap="plasma", alpha=0.85)
plt.colorbar(scatter, ax=ax1, label="Density", shrink=0.8)

# STYLE + AXIS
ax1.set_xlim(valid_data[X_VAR].quantile([0.01, 0.99]))
ax1.set_ylim(valid_data[Y_VAR].quantile([0.01, 0.99]))
ax1.set_xlabel(X_VAR, fontsize=12, color="white")
ax1.set_ylabel(Y_VAR, fontsize=12, color="white")
ax1.set_title(f"🌞 SolarPi THERMAL EYE\n({X_VAR} vs {Y_VAR})", fontsize=14, color="cyan")
ax1.grid(True, alpha=0.2, color="gray")

# 3. WIFI RSSI FRACTAL (unchanged)
rssi = df["wifi_rssi"].dropna()
ax2.plot(rssi.index, rssi.rolling(120, min_periods=1).mean(),
         color="lime", lw=2, alpha=0.9, label="Smoothed RSSI")
ax2.fill_between(rssi.index, rssi.rolling(120, min_periods=1).min(),
                 rssi.rolling(120, min_periods=1).max(),
                 color="lime", alpha=0.4, label="RSSI Envelope")
ax2.legend()
ax2.grid(True, alpha=0.3)
ax2.set_ylabel("RSSI (dBm)")
ax2.set_title("WiFi Signal Fractal")

plt.tight_layout()

print(f"\n🔥 THERMAL EYE ACTIVE: plotting {X_VAR} vs {Y_VAR}")
plt.show(block=True)
input("Press Enter to exit...")