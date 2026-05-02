import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
from requests.exceptions import RequestException
from astral import LocationInfo
from astral.location import Location
from astral.sun import sun
import pytz
from scipy.signal import convolve
from scipy.interpolate import interp1d

# ====================== CONFIGURATION ======================
FLASK_SOLAR_URL = "http://192.168.1.100:5000/solarpi/timeseries"
LAT = 38.422932
LON = -77.407997
SENSOR = 'tsl39_lux'
SATURATION_THRESHOLD = 100000  # lux above which sensor saturates
KERNEL_WIDTH = 60  # minutes for Gaussian convolution

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

# ====================== UTILITIES ======================
city = LocationInfo("Stafford", "USA", "America/New_York", LAT, LON)
loc = Location(city)
tz = pytz.timezone("America/New_York")


def get_sun_times(date):
    s = sun(city.observer, date=date, tzinfo=tz)
    sunrise = s['sunrise'].replace(tzinfo=None)
    sunset = s['sunset'].replace(tzinfo=None)
    solar_noon = sunrise + (sunset - sunrise) / 2
    return sunrise, solar_noon, sunset


def compute_solar_elevation(timestamp):
    t_local = timestamp.replace(tzinfo=tz)
    return loc.solar_elevation(t_local)


def convolution_peak(sun_elev_norm, kernel_width_minutes=60):
    time_grid = pd.date_range(sun_elev_norm.index.min(), sun_elev_norm.index.max(), freq='1min')
    f = interp1d(sun_elev_norm.index.astype(np.int64), sun_elev_norm.values,
                 kind='linear', fill_value='extrapolate')
    sun_reg = f(time_grid.astype(np.int64))
    x = np.arange(-kernel_width_minutes * 2, kernel_width_minutes * 2)
    kernel = np.exp(-0.5 * (x / kernel_width_minutes) ** 2)
    kernel /= kernel.sum()
    conv = convolve(sun_reg, kernel, mode='same')
    peak_idx = np.argmax(conv)
    peak_time = time_grid[peak_idx]
    return peak_time


# ====================== MAIN TABLE ======================
days = sorted(set(df.index.date))

print(f"\n📊 SolarPi Sensor vs Sun Position Analysis")
print(f"Sensor: {SENSOR}, Saturation threshold: {SATURATION_THRESHOLD} lux, Kernel width: {KERNEL_WIDTH} min")
print("-" * 100)
print(f"{'Date':<12} {'Sunrise':>8} {'SolarNoon':>9} {'Sunset':>8} "
      f"{'Peak':>6} {'@time':>6} {'Sat_peak':>6} {'Sat_w':>7} "
      f"{'Conv_pk':>6} {'Raw_lag':>7} {'Sat_lag':>7} {'Conv_lag':>7}")
print("-" * 100)

for day in days:
    df_day = df[df.index.date == day].copy()
    if df_day.empty or len(df_day) < 10:
        continue

    sunrise, solar_noon, sunset = get_sun_times(day)
    df_day['sun_elev'] = [compute_solar_elevation(t) for t in df_day.index]
    df_day['sun_elev_norm'] = df_day['sun_elev'].clip(lower=0) / 90.0

    # Raw sensor peak
    raw_peak = df_day[SENSOR].max()
    raw_peak_time = df_day[SENSOR].idxmax()

    # Saturation‑based peak
    sat_mask = df_day[SENSOR] > SATURATION_THRESHOLD
    if sat_mask.any():
        rise_time = df_day[sat_mask].index.min()
        fall_time = df_day[sat_mask].index.max()
        sat_midpoint = rise_time + (fall_time - rise_time) / 2
        sat_width = (fall_time - rise_time).total_seconds() / 3600
        sat_time_str = sat_midpoint.strftime('%H:%M')
        sat_width_str = f"{sat_width:.1f}"
    else:
        sat_time_str = '--'
        sat_width_str = '--'

    # Convolution peak (using only daylight)
    df_day_light = df_day[df_day['sun_elev'] > 0].copy()
    if len(df_day_light) > 10:
        conv_peak = convolution_peak(df_day_light['sun_elev_norm'], KERNEL_WIDTH)
        conv_time_str = conv_peak.strftime('%H:%M')
    else:
        conv_time_str = '--'


    # Lags (hours)
    def lag(t):
        if pd.isna(t) or t is pd.NaT:
            return '--'
        return f"{(t - solar_noon).total_seconds() / 3600:+.1f}"


    raw_lag_str = lag(raw_peak_time)
    sat_lag_str = lag(sat_midpoint) if sat_mask.any() else '--'
    conv_lag_str = lag(conv_peak) if conv_time_str != '--' else '--'

    # Print row
    print(
        f"{day.strftime('%Y-%m-%d'):<12} {sunrise.strftime('%H:%M'):>8} {solar_noon.strftime('%H:%M'):>9} {sunset.strftime('%H:%M'):>8} "
        f"{raw_peak:>6.0f} {raw_peak_time.strftime('%H:%M'):>6} {sat_time_str:>6} {sat_width_str:>7} "
        f"{conv_time_str:>6} {raw_lag_str:>7} {sat_lag_str:>7} {conv_lag_str:>7}")

print("-" * 100)

# ====================== SELF-LOCALIZATION USING CONVOLUTION PEAK ======================
print("\n🌍 Self-Localization Using Convolution Peak (No Sensor Saturation Bias)")
print("-" * 70)


def estimate_position_from_convolution(df_day, kernel_width_minutes=60, tz_offset=-4):
    """
    Estimate lat/lon using convolution of sun elevation (not raw sensor).
    Returns (lat, lon, sunrise, sunset, solar_noon) or (None,)*5.
    """
    # Resample to 1-minute
    df_min = df_day.resample('1min').mean()
    if len(df_min) < 100:
        return (None,) * 5

    # Compute sun elevation for each minute
    times = df_min.index
    elevations = []
    for t in times:
        t_local = t if t.tzinfo else t.replace(tzinfo=tz)
        elev = loc.solar_elevation(t_local)
        elevations.append(elev)
    sun_elev = np.array(elevations)
    sun_elev_norm = np.clip(sun_elev / 90.0, 0, 1)

    # Gaussian kernel
    x = np.arange(-kernel_width_minutes * 2, kernel_width_minutes * 2)
    kernel = np.exp(-0.5 * (x / kernel_width_minutes) ** 2)
    kernel /= kernel.sum()
    conv = np.convolve(sun_elev_norm, kernel, mode='same')

    # Find solar noon from convolution peak
    peak_idx = np.argmax(conv)
    solar_noon = times[peak_idx]

    # Find sunrise/sunset where conv crosses 10% of max
    threshold = 0.1
    above = conv > threshold
    if above.sum() < 10:
        return (None,) * 5
    sunrise_idx = np.argmax(above)
    sunset_idx = len(above) - 1 - np.argmax(above[::-1])
    sunrise = times[sunrise_idx]
    sunset = times[sunset_idx]

    # Daylight length check
    daylight_hours = (sunset - sunrise).total_seconds() / 3600
    if daylight_hours < 4 or daylight_hours > 16:
        return (None,) * 5

    # Longitude from solar noon (convolution peak)
    solar_noon_utc = solar_noon - pd.Timedelta(hours=tz_offset)
    solar_noon_hours = solar_noon_utc.hour + solar_noon_utc.minute / 60
    estimated_lon = (solar_noon_hours - 12.0) * 15.0
    if estimated_lon > 180: estimated_lon -= 360
    if estimated_lon < -180: estimated_lon += 360

    # Latitude from daylight length
    doy = df_day.index[0].timetuple().tm_yday
    declination = -23.45 * np.cos(2 * np.pi * (doy + 10) / 365)
    decl_rad = np.deg2rad(declination)
    daylight_fraction = daylight_hours / 24.0
    if abs(daylight_fraction) > 0.999: daylight_fraction = 0.999
    cos_lat = np.sin(decl_rad) / np.cos(daylight_fraction * np.pi)
    cos_lat = np.clip(cos_lat, -1, 1)
    estimated_lat = np.rad2deg(np.arccos(cos_lat))

    return estimated_lat, estimated_lon, sunrise, sunset, solar_noon


lat_ests = []
lon_ests = []

for day in days:
    df_day = df[df.index.date == day].copy()
    if len(df_day) < 100:
        continue
    lat, lon, sr, ss, sn = estimate_position_from_convolution(df_day)
    if lat is not None:
        lat_ests.append(lat)
        lon_ests.append(lon)
        print(f"{day.strftime('%Y-%m-%d'):<12} Solar noon: {sn.strftime('%H:%M')} "
              f"Sunrise: {sr.strftime('%H:%M')} Sunset: {ss.strftime('%H:%M')} "
              f"Daylight: {((ss - sr).total_seconds() / 3600):.1f}h → Est. Lat: {lat:.1f}°, Lon: {lon:.1f}°")

if lat_ests:
    avg_lat = np.mean(lat_ests)
    avg_lon = np.mean(lon_ests)
    std_lat = np.std(lat_ests)
    std_lon = np.std(lon_ests)
    print("-" * 70)
    print(f"📌 Average estimated position: {avg_lat:.1f}°N, {abs(avg_lon):.1f}°{'W' if avg_lon < 0 else 'E'}")
    print(f"   Standard deviation: lat ±{std_lat:.1f}°, lon ±{std_lon:.1f}°")
    print(f"   True position (Stafford, VA): 38.4°N, 77.4°W")
    print(f"   Error: {abs(avg_lat - 38.4):.1f}° in latitude, {abs(avg_lon + 77.4):.1f}° in longitude")
else:
    print("Not enough valid days for localization.")