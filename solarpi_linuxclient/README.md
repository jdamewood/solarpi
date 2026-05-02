## Linux Client Scripts (`solarpi_linuxclient/`)

| File Name                           | Description                                                                                                                                     |
|-------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|
| `TSL2561heatmap_res.py`             | Generates high‑resolution heatmaps of TSL2561 light sensor data (lux vs time of day). Uses 30‑second binning and colormaps to visualise daily light patterns. |
| `sensor_convolve_sun_positon.py`    | Compares sensor readings (e.g., lux, temperature) with solar elevation. Computes convolution of sunlight with a Gaussian kernel, determines solar noon, and optionally estimates latitude/longitude from the light curve. |
| `sensorbatterystatsjson.py`         | Main daily statistics script. Fetches data from the Flask endpoint (`/solarpi/timeseries`), computes battery energy, buck efficiency, SoC, and prints a detailed daily dashboard. |
| `sensorbatterystatsjson1.py`        | Variant of the daily stats script – possibly an earlier version or one with different smoothing / threshold settings.                              |
| `sensorbatterystatsjson2.py`        | Another variant of the daily stats script – may include additional metrics or plot exports.                                                      |
| `sensorstats.py`                    | General sensor statistics and visualisation script. Likely analyses current, voltage, light, and temperature data, producing summary tables and histograms. |
| `sensorstats_Gaussian.py`           | Extended version of `sensorstats.py` that applies Gaussian smoothing or kernel density estimation to sensor data for trend analysis.             |
| `solarjsonclient.c`                 | C source code for the plain‑socket client that runs on the Linux PC. Connects to the Pi on port 5005, sends `"go"`, and saves JSON/CSV logs.   |
| `solarlogheatmap.py`                | Creates 2D heatmaps of sensor values (e.g., current, voltage, temperature) over time, using a configurable time‑binning and colormap.           |
| `solarpijsonclient.py`              | Python version of the socket client (alternative to the compiled C binary). Connects to the Pi’s socket server and logs data to JSON/CSV.       |
| `waterfall_kernelbin.py`            | Generates 3D waterfall plots with adjustable kernel binning (e.g., Gaussian smoothing). Useful for visualising daily and seasonal trends.       |
| `waterfallplots.py`                 | Produces 3D waterfall plots for multiple sensors (e.g., BME temperature, battery voltage, light channels) with user‑selectable resolution and lighting effects. |
