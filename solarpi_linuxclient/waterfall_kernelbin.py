import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
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
    df = df.set_index('timestamp').sort_index().reset_index()  # keep timestamp column
    print(f"✅ Loaded {len(df)} records")
except RequestException as e:
    print(f"❌ Failed to fetch data: {e}")
    exit(1)

# Keep only the last ~48 hours (approximately last 80% of rows, as original logic)
# Original: df = df.tail(int(len(df) * 0.8))
# That selects the most recent 80% of rows.
# To mimic that, we sort by timestamp (already done) and take tail.
df = df.tail(int(len(df) * 0.8))

df["hour_of_day"] = df["timestamp"].dt.hour + df["timestamp"].dt.minute / 60.0
df["day_of_period"] = (df["timestamp"] - df["timestamp"].min()).dt.total_seconds() / 3600.0

sensor_columns = ["tsl39_ch0", "tsl39_ch1", "tsl29_ch0", "tsl29_ch1"]
# Check which columns actually exist in the fetched data
existing_sensor_cols = [col for col in sensor_columns if col in df.columns]
if not existing_sensor_cols:
    print("⚠️ None of the expected TSL sensor columns found. Available columns:", df.columns.tolist())
    # Fallback: use any TSL columns that are present (maybe different names)
    existing_sensor_cols = [col for col in df.columns if 'tsl' in col.lower()]
    print(f"Using fallback sensor columns: {existing_sensor_cols}")

if not existing_sensor_cols:
    raise RuntimeError("No TSL sensor data available – cannot proceed.")

plt.figure(figsize=(16, 12))

# 48hr Time Series (New!)
plt.subplot(3, 2, 1)
for col in existing_sensor_cols:
    plt.plot(df["day_of_period"], df[col], alpha=0.7, label=col)
plt.xlabel("Hours (Last 48)")
plt.ylabel("Raw Counts")
plt.title("48-Hour TSL2561 Trends")
plt.legend()
plt.grid(True, alpha=0.3)

# Original KDEs (2x2 grid)
for i, col in enumerate(existing_sensor_cols, 3):
    if i > 6:  # Only up to 4 subplots (positions 3,4,5,6)
        break
    plt.subplot(3, 2, i)
    sns.kdeplot(
        x=df["hour_of_day"], y=df[col], fill=True, cmap="viridis",
        bw_adjust=0.5, thresh=0.05, levels=100
    )
    plt.xlabel("Hour of Day")
    plt.ylabel(f"{col}")
    plt.title(f"48hr Density: {col}")
    plt.xlim(0, 24)

# Day/Night Separation (FIXED)
plt.subplot(3, 2, 6)
day_mask = (df["hour_of_day"] >= 8) & (df["hour_of_day"] <= 18)
night_mask = ~day_mask

# Use the first available TSL sensor for day/night plot, e.g., tsl39_ch0 if present
primary_sensor = "tsl39_ch0"
if primary_sensor not in df.columns and existing_sensor_cols:
    primary_sensor = existing_sensor_cols[0]
else:
    # fallback: use any existing sensor
    primary_sensor = existing_sensor_cols[0] if existing_sensor_cols else None

if primary_sensor:
    sns.kdeplot(x=df[day_mask]["hour_of_day"], y=df[day_mask][primary_sensor],
                fill=True, cmap="Reds", alpha=0.8, label="Day")
    sns.kdeplot(x=df[night_mask]["hour_of_day"], y=df[night_mask][primary_sensor],
                fill=True, cmap="Blues", alpha=0.8, label="Night")
    plt.xlabel("Hour of Day")
    plt.ylabel(primary_sensor)
    plt.title("Day vs Night Separation (48hr)")
    plt.xlim(0, 24)
    plt.legend()
else:
    plt.text(0.5, 0.5, "No TSL sensor data for day/night plot", ha='center', va='center')
    plt.axis('off')

plt.tight_layout()
plt.savefig("solarpi_48hr_light_analysis.png", dpi=300, bbox_inches='tight')
plt.show()

total_hours = df["day_of_period"].max()
print(f"Analyzed {len(df)} samples over ~{total_hours:.1f} hours")