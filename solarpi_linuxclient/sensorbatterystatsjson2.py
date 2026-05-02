import pandas as pd
import numpy as np
import requests
import os
import logging
import time
from datetime import datetime

# ======================================================================================
# CONFIGURATION
# ======================================================================================
FLASK_SOLAR_URL = "http://192.168.1.100:5000/solarpi/timeseries"
FLASK_ESP8266_URL = "http://192.168.1.100:5000/esp8266"

DAYS_BACK = 48  # Can be overridden by environment variable
ENABLE_PLOTS = True  # Set to False if matplotlib not available

# Create output directory BEFORE logging setup
os.makedirs("output", exist_ok=True)

# Setup logging - fix Windows encoding issues (harmless on Linux)
class SafeStreamHandler(logging.StreamHandler):
    """Stream handler that replaces unsupported characters"""

    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # Replace emoji and other Unicode characters for Windows console
            msg = msg.replace('✅', '[OK]')
            msg = msg.replace('⚠️', '[WARN]')
            msg = msg.replace('📊', '[DATA]')
            msg = msg.replace('🔋', '[BAT]')
            msg = msg.replace('💾', '[SAVE]')
            stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


# Remove any existing handlers
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('output/sensor_analysis.log', encoding='utf-8'),
        SafeStreamHandler()
    ]
)
logger = logging.getLogger(__name__)

KEY_COLS = [
    "ina44_v_mean",
    "ina44_v_min",
    "ina44_v_max",
    "ina44_i_mean",
    "ina44_i_min",
    "ina44_i_max",
    "ina44_i_rms",
    "ina45_v_mean",
    "ina45_v_min",
    "ina45_v_max",
    "ina45_i_mean",
    "ina45_i_min",
    "ina45_i_max",
    "bus_voltage_v_mean",
    "bus_voltage_v_min",
    "bus_voltage_v_max",
    "bus_voltage_v_range",
    "esp_current_ma_mean",
    "esp_current_ma_min",
    "esp_current_ma_max",
    "Battery_error_pct_mean",
    "Battery_error_pct_min",
    "Battery_error_pct_max",
    "solar_Wh",
    "usb5_Wh",
    "battery_Wh",
]

# Physical limits for data validation
LIMITS = {
    'ina44_v': (0, 30),  # Voltage range (0-30V)
    'ina44_i': (0, 500),  # Current range (0-500mA)
    'ina45_v': (0, 6),  # USB voltage (0-6V)
    'ina45_i': (0, 500),  # USB current (0-500mA)
    'bus_voltage_v': (10, 15),  # Battery voltage (10-15V for 4S LiFePO4)
    'esp_current_ma': (-3000, 3000),  # Battery current range (-3A to +3A)
    'Battery_error_pct': (-10, 10),  # Plausible error percentage
}


# ======================================================================================
# HELPER: average sample period in seconds
# ======================================================================================
def avg_sample_period_s(ts_index):
    """Calculate average sample period with outlier filtering"""
    if len(ts_index) < 2:
        return 1.0  # default assumption

    dt = ts_index.to_series().diff().dropna()
    if dt.empty:
        return 1.0

    # Filter out outliers (e.g., > 3 * median)
    median_dt = dt.median()
    if median_dt.total_seconds() > 0:
        filtered = dt[dt <= median_dt * 3]
        m = filtered.mean() if not filtered.empty else dt.mean()
        return m.total_seconds() if pd.notna(m) else 1.0
    return 1.0


# ======================================================================================
# HELPER: clean and validate measurements
# ======================================================================================
def clean_measurements(df, source_name):
    """Apply physical limits and clean sensor data"""
    if df.empty:
        return df

    original_count = len(df)
    logger.info(f"Cleaning {source_name} data: {original_count} records")

    for col, (min_val, max_val) in LIMITS.items():
        if col in df.columns:
            # Flag out-of-range values
            out_of_range = ((df[col] < min_val) | (df[col] > max_val))
            if out_of_range.any():
                logger.warning(f"  {col}: {out_of_range.sum()} out-of-range values replaced with NaN")
                df.loc[out_of_range, col] = np.nan

    # Special handling for currents - small noise elimination
    if "ina44_i" in df.columns:
        # Solar current can't be negative, set to 0 if slightly negative
        df.loc[df["ina44_i"] < 0, "ina44_i"] = 0
        # Eliminate noise near zero (treat < 2mA as 0)
        df.loc[df["ina44_i"].abs() < 2, "ina44_i"] = 0

    if "ina45_i" in df.columns:
        df.loc[df["ina45_i"] < 0, "ina45_i"] = 0
        df.loc[df["ina45_i"].abs() < 2, "ina45_i"] = 0

    if "esp_current_ma" in df.columns:
        # Keep sign (positive = charge, negative = discharge)
        # Eliminate noise near zero
        df.loc[df["esp_current_ma"].abs() < 5, "esp_current_ma"] = 0

    cleaned_count = df.dropna(how='all').shape[0]
    logger.info(f"  Kept {cleaned_count}/{original_count} records after cleaning")

    return df


# ======================================================================================
# HELPER: fetch and index JSON
# ======================================================================================
def fetch_json(url, source_name, timeout=30):
    """Fetch JSON data from endpoint with retry logic"""
    logger.info(f"Fetching data from {source_name}...")

    for attempt in range(3):  # Retry up to 3 times
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            data = r.json()

            if not data:
                logger.warning(f"Empty response from {source_name}")
                return pd.DataFrame(index=pd.DatetimeIndex([]))

            df = pd.DataFrame(data)

            # Handle timestamp column
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
                df = df.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
            elif "time" in df.columns:
                df["timestamp"] = pd.to_datetime(df["time"], errors="coerce")
                df = df.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
            else:
                # Create dummy timestamps if none exist
                df.index = pd.date_range(
                    start=datetime.now() - pd.Timedelta(hours=len(df)),
                    periods=len(df),
                    freq='min'
                )

            logger.info(f"[OK] Fetched {len(df)} records from {source_name}")
            return df

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on attempt {attempt + 1}/3 for {source_name}")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Connection error on attempt {attempt + 1}/3: {e}")
        except Exception as e:
            logger.error(f"Failed to fetch from {source_name}: {type(e).__name__}: {e}")

        if attempt < 2:
            time.sleep(2 ** attempt)  # Exponential backoff

    return pd.DataFrame(index=pd.DatetimeIndex([]))


# ======================================================================================
# FETCH DATA
# ======================================================================================
# Override DAYS_BACK from environment if set
DAYS_BACK = int(os.environ.get("DAYS_BACK", DAYS_BACK))

df_solar = fetch_json(FLASK_SOLAR_URL, "SolarPi main")
df_esp = fetch_json(FLASK_ESP8266_URL, "ESP8266 battery monitor")

# Clean the data
df_solar = clean_measurements(df_solar, "SolarPi")
df_esp = clean_measurements(df_esp, "ESP8266")

# ======================================================================================
# ALIGNED FRAME: SolarPi index, ESP aligned to nearest time
# ======================================================================================
if df_solar.empty:
    logger.error("No SolarPi data available. Exiting.")
    exit(1)

idx = df_solar.index

df = pd.DataFrame(index=idx)
df["ina44_v"] = df_solar["ina44_v"]
df["ina44_i"] = df_solar["ina44_i"]
df["ina45_v"] = df_solar["ina45_v"]
df["ina45_i"] = df_solar["ina45_i"]

# Pull ESP values at the nearest matching SolarPi timestamp with time window check
if not df_esp.empty:
    # Use reindex with method='nearest' for alignment
    # First, create a common index by merging
    try:
        # Align ESP data to SolarPi timestamps using nearest neighbor
        df_esp_aligned = df_esp.reindex(idx, method='nearest', tolerance=pd.Timedelta(minutes=5))

        df["bus_voltage_v"] = df_esp_aligned["bus_voltage_v"]
        df["esp_current_ma"] = df_esp_aligned["esp_current_ma"] if "esp_current_ma" in df_esp_aligned.columns else (
            df_esp_aligned["current_a"] * 1000 if "current_a" in df_esp_aligned.columns else np.nan
        )

        # Count how many matches we got within tolerance
        valid_matches = df["bus_voltage_v"].notna().sum()
        logger.info(f"Aligned {valid_matches} ESP records to SolarPi timestamps (within 5 min tolerance)")

    except Exception as e:
        logger.error(f"Error aligning ESP data: {e}")
        logger.info("Falling back to asof method...")

        # Fallback: use asof for each index value
        df["bus_voltage_v"] = df_esp["bus_voltage_v"].asof(idx)
        df["esp_current_ma"] = df_esp["esp_current_ma"].asof(idx) if "esp_current_ma" in df_esp.columns else (
            df_esp["current_a"].asof(idx) * 1000 if "current_a" in df_esp.columns else np.nan
        )

        # Check time difference for asof method
        esp_idx_at_match = pd.Series(index=idx, dtype='object')
        for i, t in enumerate(idx):
            # Find nearest index in esp
            nearest_idx = df_esp.index.asof(t)
            if nearest_idx is not None:
                esp_idx_at_match.iloc[i] = nearest_idx

        # Convert to datetime and calculate difference
        esp_idx_at_match = pd.to_datetime(esp_idx_at_match)
        time_diff = idx - esp_idx_at_match
        stale_data = time_diff > pd.Timedelta(minutes=5)
        if stale_data.any():
            logger.warning(f"Marking {stale_data.sum()} records as stale (time diff > 5 min)")
            df.loc[stale_data, ["bus_voltage_v", "esp_current_ma"]] = np.nan
else:
    logger.warning("No ESP8266 data available - battery measurements will be missing")

# ======================================================================================
# CALCULATE BATTERY ERROR PERCENTAGE
# ======================================================================================
# Add hysteresis and sanity checks for battery error calculation
both_bus = (
        df["bus_voltage_v"].notna() &
        df["ina44_v"].notna() &
        (df["bus_voltage_v"] != 0.0) &
        (df["bus_voltage_v"] > LIMITS['bus_voltage_v'][0]) &  # Min plausible voltage
        (df["bus_voltage_v"] < LIMITS['bus_voltage_v'][1])  # Max plausible voltage
)

# Calculate error only when difference is significant and not due to measurement error
voltage_diff = df["bus_voltage_v"] - df["ina44_v"]
df["Battery_error_pct"] = np.where(
    both_bus & (voltage_diff.abs() < 1.0),  # Ignore errors > 1V as likely measurement error
    voltage_diff / df["bus_voltage_v"] * 100.0,
    np.nan
).round(2)

logger.info(f"\nSample Battery_error_pct (non-NaN only): {len(df['Battery_error_pct'].dropna())} records")
if len(df['Battery_error_pct'].dropna()) > 0:
    logger.info(df["Battery_error_pct"].dropna().head(20).to_string())

# ======================================================================================
# DAILY STATISTICS
# ======================================================================================
cols_to_analyze = [
    "ina44_v",
    "ina44_i",
    "ina45_v",
    "ina45_i",
    "bus_voltage_v",
    "esp_current_ma",
    "Battery_error_pct",
]

if df.empty or df.index.isna().all():
    daily_stats = pd.DataFrame()
    logger.error("No data available for daily statistics")
else:
    max_ts = df.index.max()
    if pd.notna(max_ts):
        cutoff = max_ts.normalize() - pd.Timedelta(days=DAYS_BACK)
        df_recent = df[df.index >= cutoff]
        logger.info(f"Analyzing {len(df_recent)} records from last {DAYS_BACK} days")
    else:
        df_recent = df

    # Basic daily stats on all channels
    daily = df_recent[cols_to_analyze].groupby(df_recent.index.date)
    daily_stats_mi = daily.agg(["mean", "std", "min", "max"]).round(3)

    # INA44_I RMS
    daily = df_recent[["ina44_i"]].groupby(df_recent.index.date)
    daily_stats_mi[("ina44_i", "rms")] = daily["ina44_i"].apply(
        lambda x: np.sqrt(np.mean(x ** 2)) if len(x) > 0 else np.nan
    ).round(6)

    # INA45_I RMS
    daily = df_recent[["ina45_i"]].groupby(df_recent.index.date)
    daily_stats_mi[("ina45_i", "rms")] = daily["ina45_i"].apply(
        lambda x: np.sqrt(np.mean(x ** 2)) if len(x) > 0 else np.nan
    ).round(6)

    # Bus voltage range
    if ("bus_voltage_v", "max") in daily_stats_mi.columns and ("bus_voltage_v", "min") in daily_stats_mi.columns:
        daily_stats_mi[("bus_voltage_v", "range")] = (
                daily_stats_mi[("bus_voltage_v", "max")]
                - daily_stats_mi[("bus_voltage_v", "min")]
        )

    # 3‑sigma bands for current measurements
    for col in ["ina44_i", "ina45_i", "esp_current_ma"]:
        mn = f"{col}_mean"
        sd = f"{col}_std"
        if mn in daily_stats_mi.columns and sd in daily_stats_mi.columns:
            daily_stats_mi[f"{col}_3sigma_lo"] = daily_stats_mi[mn] - 3 * daily_stats_mi[sd]
            daily_stats_mi[f"{col}_3sigma_hi"] = daily_stats_mi[mn] + 3 * daily_stats_mi[sd]

    # Data quality metrics
    sample_period = avg_sample_period_s(df_recent.index)
    expected_samples_per_day = 24 * 3600 / sample_period if sample_period > 0 else 86400

    daily_stats_mi[("data_completeness_pct", "")] = df_recent.groupby(df_recent.index.date).apply(
        lambda x: (len(x) / expected_samples_per_day) * 100
    ).round(1)

    daily_stats_mi[("negative_current_detected_ina44", "")] = df_recent.groupby(df_recent.index.date).apply(
        lambda x: (x["ina44_i"] < 0).any()
    )

    if "esp_current_ma" in df_recent.columns:
        daily_stats_mi[("negative_current_detected_esp", "")] = df_recent.groupby(df_recent.index.date).apply(
            lambda x: (x["esp_current_ma"] < 0).any()
        )
    else:
        daily_stats_mi[("negative_current_detected_esp", "")] = False

    # Flatten multi-index columns
    daily_stats = daily_stats_mi.copy()
    daily_stats.columns = ["_".join(filter(None, map(str, c))) for c in daily_stats.columns]

# ======================================================================================
# ENERGY INTEGRALS
# ======================================================================================
solar_period_s = avg_sample_period_s(df.index)
esp_period_s = avg_sample_period_s(df_esp.index) if not df_esp.empty else 1.0

solar_dt_h = solar_period_s / 3600.0
esp_dt_h = esp_period_s / 3600.0

logger.info(f"\nAverage SolarPi sample period: {solar_period_s:.2f} s")
logger.info(f"Average ESP8266 sample period: {esp_period_s:.2f} s")

df["solar_power_w"] = df["ina44_v"] * df["ina44_i"] / 1000
df["usb5_power_w"] = df["ina45_v"] * df["ina45_i"] / 1000
df["battery_power_w"] = df["bus_voltage_v"] * df["esp_current_ma"] / 1000

daily_energy = df.groupby(df.index.date).agg(
    solar_Wh=("solar_power_w", lambda x: (x * solar_dt_h).sum()),
    usb5_Wh=("usb5_power_w", lambda x: (x * solar_dt_h).sum()),
    battery_Wh=("battery_power_w", lambda x: (x * esp_dt_h).sum()),
).round(3)

# Combine daily stats with energy data
if not daily_stats.empty:
    daily_stats = daily_stats.join(daily_energy, how="outer")
else:
    daily_stats = daily_energy

# ======================================================================================
# DATA QUALITY SUMMARY
# ======================================================================================
logger.info("\n" + "=" * 80)
logger.info("[DATA] DATA QUALITY SUMMARY")
logger.info("=" * 80)

if not daily_stats.empty:
    # Days with complete battery data
    if "bus_voltage_v_mean" in daily_stats.columns:
        complete_days = daily_stats["bus_voltage_v_mean"].notna().sum()
        total_days = len(daily_stats)
        logger.info(f"Days with battery data: {complete_days}/{total_days} ({100 * complete_days / total_days:.1f}%)")

    # Negative current detection
    if "negative_current_detected_ina44" in daily_stats.columns:
        neg_ina44 = daily_stats["negative_current_detected_ina44"].sum()
        logger.info(f"Days with negative solar current (INA44): {neg_ina44}")

    if "negative_current_detected_esp" in daily_stats.columns:
        neg_esp = daily_stats["negative_current_detected_esp"].sum()
        logger.info(f"Days with negative battery current (ESP): {neg_esp}")

    # Energy balance check
    if "solar_Wh" in daily_stats.columns and "battery_Wh" in daily_stats.columns:
        total_solar = daily_stats["solar_Wh"].sum()
        total_battery_discharge = daily_stats["battery_Wh"][daily_stats["battery_Wh"] < 0].sum()
        total_battery_charge = daily_stats["battery_Wh"][daily_stats["battery_Wh"] > 0].sum()

        logger.info(f"\n[BAT] Energy Summary:")
        logger.info(f"  Total solar energy: {total_solar / 1000:.2f} kWh")
        logger.info(f"  Total battery discharge: {abs(total_battery_discharge) / 1000:.2f} kWh")
        logger.info(f"  Total battery charge: {total_battery_charge / 1000:.2f} kWh")
        logger.info(f"  Net battery change: {(total_battery_charge + total_battery_discharge) / 1000:.2f} kWh")

        # Energy efficiency (if applicable)
        if total_solar > 0:
            efficiency = (abs(total_battery_discharge) / total_solar) * 100
            logger.info(f"  Solar to battery efficiency: {efficiency:.1f}%")

    # Battery error statistics
    if "Battery_error_pct_mean" in daily_stats.columns:
        valid_errors = daily_stats["Battery_error_pct_mean"].dropna()
        if len(valid_errors) > 0:
            logger.info(f"\n[BAT] Battery Voltage Error Statistics:")
            logger.info(f"  Mean error: {valid_errors.mean():.2f}%")
            logger.info(f"  Std deviation: {valid_errors.std():.2f}%")
            logger.info(f"  Max error: {valid_errors.max():.2f}%")
            logger.info(f"  Min error: {valid_errors.min():.2f}%")

# ======================================================================================
# PRINT AND SAVE RESULTS
# ======================================================================================
print("\n" + "=" * 80)
print("[DATA] DAILY SENSOR STATISTICS (last {} days)".format(DAYS_BACK))
print("=" * 80)

available_cols = [c for c in KEY_COLS if c in daily_stats.columns]
if available_cols:
    # Show only key columns for cleaner output
    print(daily_stats[available_cols].round(3).to_string())
else:
    print("No key columns found. Available columns:")
    print(daily_stats.columns.tolist())

# Save to CSV
os.makedirs("output", exist_ok=True)  # Already exists, but safe to call again
daily_stats.to_csv("output/daily_sensor_statistics_last_{}_days.csv".format(DAYS_BACK))
logger.info(f"\n[SAVE] Data saved to output/daily_sensor_statistics_last_{DAYS_BACK}_days.csv")

# ======================================================================================
# DIAGNOSTIC PLOTS (optional)
# ======================================================================================
if ENABLE_PLOTS:
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        logger.info("\n[DATA] Generating diagnostic plots...")

        fig, axes = plt.subplots(4, 1, figsize=(14, 10))
        fig.suptitle('Solar Power System Diagnostics', fontsize=16, fontweight='bold')

        # Plot 1: Voltage comparison
        ax1 = axes[0]
        # Downsample for plotting if too many points (>50000)
        plot_idx = idx
        if len(idx) > 50000:
            plot_idx = idx[::10]  # Take every 10th point
            logger.info("Downsampling voltage plot (every 10th point)")

        ax1.plot(plot_idx, df.loc[plot_idx, "ina44_v"], label="INA44 (Solar)", alpha=0.7, linewidth=0.5)
        ax1.plot(plot_idx, df.loc[plot_idx, "bus_voltage_v"], label="ESP (Battery)", alpha=0.7, linewidth=0.5)
        ax1.set_ylabel("Voltage (V)")
        ax1.legend(loc='best')
        ax1.grid(True, alpha=0.3)
        ax1.set_title("Voltage Measurements")

        # Plot 2: Currents
        ax2 = axes[1]
        ax2.plot(plot_idx, df.loc[plot_idx, "ina44_i"], label="Solar Current", alpha=0.7, linewidth=0.5)
        ax2.plot(plot_idx, df.loc[plot_idx, "ina45_i"], label="USB Current", alpha=0.7, linewidth=0.5)
        ax2.set_ylabel("Current (mA)")
        ax2.legend(loc='best')
        ax2.grid(True, alpha=0.3)
        ax2.set_title("Current Measurements")

        # Plot 3: Battery current and error
        ax3 = axes[2]
        ax3.plot(plot_idx, df.loc[plot_idx, "esp_current_ma"], label="Battery Current", alpha=0.7, linewidth=0.5,
                 color='green')
        ax3.set_ylabel("Battery Current (mA)")
        ax3.legend(loc='best')
        ax3.grid(True, alpha=0.3)
        ax3.set_title("Battery Current")

        # Plot 4: Battery error percentage
        ax4 = axes[3]
        ax4.plot(plot_idx, df.loc[plot_idx, "Battery_error_pct"], label="Battery Error %", alpha=0.7, linewidth=0.5,
                 color='red')
        ax4.set_ylabel("Error (%)")
        ax4.axhline(y=0, color='k', linestyle='--', alpha=0.3)
        ax4.legend(loc='best')
        ax4.grid(True, alpha=0.3)
        ax4.set_title("Voltage Measurement Error (ESP vs INA44)")

        # Format x-axis for all subplots
        for ax in axes:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            ax.xaxis.set_major_locator(mdates.WeekdayLocator())
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

        plt.tight_layout()
        plt.subplots_adjust(top=0.95)
        plt.savefig("output/sensor_diagnostics.png", dpi=150, bbox_inches='tight')
        logger.info("[OK] Diagnostic plot saved to output/sensor_diagnostics.png")

        # Optional: Create a second plot for energy
        if not daily_energy.empty and len(daily_energy) > 1:
            fig2, ax = plt.subplots(figsize=(12, 6))
            days = pd.to_datetime(daily_energy.index)
            ax.bar(days - pd.Timedelta(days=0.3), daily_energy['solar_Wh'], width=0.6, label='Solar Energy', alpha=0.7)
            ax.bar(days, daily_energy['battery_Wh'], width=0.6, label='Battery Energy', alpha=0.7)
            ax.bar(days + pd.Timedelta(days=0.3), daily_energy['usb5_Wh'], width=0.6, label='USB Energy', alpha=0.7)
            ax.set_xlabel('Date')
            ax.set_ylabel('Energy (Wh)')
            ax.set_title('Daily Energy Production/Consumption')
            ax.legend()
            ax.grid(True, alpha=0.3)
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            plt.savefig("output/daily_energy.png", dpi=150, bbox_inches='tight')
            logger.info("[OK] Energy plot saved to output/daily_energy.png")

    except ImportError:
        logger.warning("[WARN] matplotlib not installed - skipping diagnostic plots")
    except Exception as e:
        logger.error(f"Failed to generate plots: {e}")

logger.info("\n[OK] Analysis complete!")