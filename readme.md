## ⚠️ Disclaimer

**This project is provided “AS‑IS” for educational and informational purposes only. The author makes no warranties, express or implied, regarding the safety, reliability, or suitability of the code for any specific application. You are solely responsible for any use or misuse of the software and hardware described here. Working with batteries, solar panels, and electrical systems can be dangerous and may cause property damage, injury, or death if not done correctly. The author disclaims all liability for any damages or injuries arising from the use or misuse of this project. No technical support is provided.**

This code is released under the **MIT License** (see the `LICENSE` file). You are free to use, modify, and distribute it, but there is no warranty.

---
## 1. I²C Sensor Map

| Address | Device  | Sensor Type                     | Status / Role                                  |
|---------|---------|---------------------------------|------------------------------------------------|
| 0x29    | TSL2561 | Light (CH0/CH1, Lux)            | Active – primary light sensor                  |
| 0x39    | TSL2561 | Light (CH0/CH1, Lux)            | Active – secondary light sensor                |
| 0x40    | HDC1000 | Temperature / Humidity          | **Replaced** by BME280 (2026-03-09)            |
| 0x76    | BME280  | Temp/Humidity/Pressure          | Active - Temp/Humidity/Pressure                |
| 0x41    | INA219  | Current / Voltage               | **Disconnected** – floating, readings ignored  |
| 0x44    | INA219  | Current / Voltage               | Active – battery bus (buck input)              |
| 0x45    | INA219  | Current / Voltage               | Active – 5 V USB rail (Pi power consumption)   |

## 2. Power Hardware

| Component          | Details                                                                 |
|--------------------|-------------------------------------------------------------------------|
| Battery            | 20 Ah LiPo (upgraded from 5 Ah on 2025-12-06)                           |
| Solar Panel        | 40 W mono/poly (upgraded 2026-02-04)                                    |
| Charge Controller  | BougeRV Li 10A PWM, adjustable for LiFePO₄                              |
| Buck Converter     | DROK 5A (6‑36 V input → 5.1 V output) – powers Raspberry Pi via USB     |
| Capacitor Bank     | 16 V, 20 F (removed 2026-03-22)                                         |

## 3. Software & Services

### On Raspberry Pi (SolarPi) – `powertest.service`

| Setting          | Value                                       |
|------------------|---------------------------------------------|
| ExecStart        | `python3 powertest_server_json.py`          |
| Type             | simple                                      |
| Restart          | always (2 s delay)                          |
| WorkingDirectory | `/home/pi/sensors`                          |
| Logs             | `powertest.log` (append)                    |
| Flask endpoints  | `/solarpi/timeseries` and `/esp8266` (JSON) |

**Check if service is running:**
```bash
sudo systemctl status powertest.service
```
## 4. Data Processing Script

**`python3 sensorbatterystatsjson.py`**  


```
Fetches data from both Flask endpoints, computes daily statistics:

- Pi energy consumption (`PiWh`)
- Net battery energy (`NetWh`)
- Battery voltage min/max (`BatVmin` / `BatVmax`)
- Average buck efficiency (`Buck%`, ~62%)
- SoC from ESP8266 Coulomb counting (anchored at ≥14.2 V, low net current)
- USB5V rail voltage & current min/max
- BME280 temperature min/max/avg

```python sensorbatterystatsjson.py
Fetching data from SolarPi main...
✅ Fetched 119871 records from SolarPi main
Fetching data from ESP8266 battery monitor...
✅ Fetched 325021 records from ESP8266 battery monitor

💥 SolarPi columns:
 ['bme_hum', 'bme_press', 'bme_temp', 'cpu_temp', 'ina41_i', 'ina41_v', 'ina44_i', 'ina44_v', 'ina45_i', 'ina45_v', 'read_time', 'tsl29_ch0', 'tsl29_ch1', 'tsl29_lux', 'tsl39_ch0', 'tsl39_ch1', 'tsl39_lux', 'wifi_rssi']
💥 ESP8266 columns:
 ['bus_voltage_v', 'current_a', 'current_ma', 'ip_address', 'load_voltage_v', 'power_mw', 'power_w', 'rssi_dbm', 'shunt_voltage_mv', 'shunt_voltage_v', 'time', 'status']

🔍 Diagnostic: On 2026-04-23, ESP8266 max voltage = 14.708 V
   ✓ High voltage detected – raw data seems correct.
✅ Unified temp: bme_temp only
• Temp (BME280): 21.3°C avg (min -3.0°C) [119,871 samples]
🔋 First Coulomb anchor at 2026-03-25 15:02:00 (≥14.2V, net current ≤200mA for 10 min)

📊 TODAY'S HOURLY SNAPSHOT (Current 12V Battery Bus)
                        Pi_Wh  Bat_V   Net_mA
timestamp                                    
2026-05-01 00:00:00  0.839952  13.10  -137.24
2026-05-01 01:00:00  0.842634  13.09  -137.21
2026-05-01 02:00:00  0.839707  13.08  -137.22
2026-05-01 03:00:00  0.838391  13.07  -138.86
2026-05-01 04:00:00  0.838172  13.06  -137.32
2026-05-01 05:00:00  0.837919  13.05  -136.71
2026-05-01 06:00:00  0.840150  13.05  -130.67
2026-05-01 07:00:00  0.835739  13.05  -112.97
2026-05-01 08:00:00  0.847400  13.06   -98.01
2026-05-01 09:00:00  0.839846  13.07   -86.16
2026-05-01 10:00:00  0.844868  13.09   -66.44
2026-05-01 11:00:00  0.851041  13.10   -42.42
2026-05-01 12:00:00  0.853875  13.12   -14.34
2026-05-01 13:00:00  0.915759  13.14    14.26
2026-05-01 14:00:00  0.896784  13.42   903.83
2026-05-01 15:00:00  0.915669  13.64  1458.21
2026-05-01 16:00:00  0.910230  13.60  1066.83
2026-05-01 17:00:00  0.885935  13.36    32.40
2026-05-01 18:00:00  0.872439  13.34   -29.45
2026-05-01 19:00:00  0.875990  13.30  -124.61
2026-05-01 20:00:00  0.869273  13.28  -139.09
2026-05-01 21:00:00  0.865406  13.27  -137.74
2026-05-01 22:00:00  0.860030  13.26  -137.78
2026-05-01 23:00:00  0.861012  13.25  -138.09

================================================================================
     ADVANCED SOLARPI DASHBOARD: 40W UPGRADE ACTIVE (ESP8266 integrated)
================================================================================
QUICK STATS (from ESP8266, after 2026-03-25):
• Total Net Battery Energy: -45 Wh
• Total Pi Consumption: 3557 Wh
• Solar Status: ✅ ACTIVE
• Critical Days (bus V < 9.3V): 1 (service days suppressed)

🔋 CAPACITOR BANK HEALTH: N/A - Cap bank intentionally removed after 2026-03-22

RECENT PERFORMANCE (Last 25 Days):
Date           PiWh  NetWh BatVmin BatVmax  Buck% Buck_min Buck_max  SoC% USB5V_Vmin USB5V_Vmax USB5V_Imin USB5V_Imax   Tmin   Tmax   Tavg
----------------------------------------------------------------------------------------------------------------------------------
2026-04-07     75.1    3.7   13.20   14.78   61.5     16.6    512.0  97.0       5.04      5.26     152.1     341.1    4.8   60.4   20.2
2026-04-08     75.0    3.3   13.19   14.77   62.3     16.6    870.9  96.9       5.07      5.44     146.9     316.1   -0.1   58.5   17.0
2026-04-09     74.6    3.5   13.20   14.76   61.8     16.5   2089.7  96.8       5.09      5.27     150.7     251.2    0.3   60.3   19.3
2026-04-10     75.2   -0.0   13.20   14.76   62.2     18.9    352.4  97.1       5.06      5.29     149.3     198.6    3.1   66.3   23.6
2026-04-11     75.6    6.4   13.22   14.76   62.2     18.1    459.0  96.8       5.06      5.24     151.7     196.5   11.8   67.2   27.6
2026-04-12     67.3    2.0   13.21   14.76   61.7     16.0    291.4  96.8       5.08      5.40     152.2     309.9    8.5   59.8   23.9
2026-04-13     42.9  -22.3   13.22   13.60   62.5     51.1     93.0  99.2*      5.09      5.14     155.8     235.7   18.3   41.4   28.5
2026-04-14     76.1   25.4   13.22   14.77   62.3     24.6     96.0  96.9       5.04      5.19     153.7     209.4   14.2   70.4   31.3
2026-04-15     75.8    3.2   13.23   14.75   62.5     22.1    422.9  96.8       5.04      5.12     155.3     263.7   16.5   70.6   31.5
2026-04-16     76.0    5.4   13.22   14.76   62.5     17.0    343.2  96.5       5.03      5.18     154.7     323.7   15.6   73.2   33.1
2026-04-17     75.8    4.3   13.23   14.78   62.4     22.0   4816.3  96.4       5.02      5.24     156.2     330.5   17.6   73.5   32.1
2026-04-18     75.2    5.2   13.22   14.73   62.1     22.9    991.4  96.1       5.03      5.23     154.6     325.8   13.3   64.8   26.9
2026-04-19     74.6    3.7   13.22   14.69   62.0     28.8    386.3  96.0       5.02      5.33     152.1     319.4    4.7   56.9   19.4
2026-04-20     74.3    6.3   13.21   14.72   61.7     19.1    245.2  95.7       5.04      5.29     149.7     331.2    2.6   59.8   16.4
2026-04-21     73.8    4.0   13.20   14.74   61.6     16.6    111.6  95.7       5.04      5.27     150.1     329.4   -1.0   61.6   16.5
2026-04-22     74.5    1.4   13.22   14.72   62.1     18.1    859.4  95.8       5.04      5.34     152.4     204.1    8.4   64.6   23.6
2026-04-23     75.0    1.2   13.22   14.71   62.0     21.7    265.6  96.0       5.04      5.34     153.9     202.9   11.2   71.7   27.0
2026-04-24     75.2   -3.0   13.23   13.70   62.2     50.4     80.5  96.5*      5.04      5.25     151.2     238.5   13.5   66.0   26.0
2026-04-25     74.2 -119.8   13.22   13.35   62.2     51.9     90.8 100.0*      5.04      5.23     151.4     254.3   11.1   26.4   16.5
2026-04-26     73.6  -91.3   13.20   13.44   61.9     46.7     84.7 100.0*      5.02      5.18     153.3     199.1    8.6   25.7   13.8
2026-04-27     74.2   74.2   13.15   13.76   62.2     47.1     90.2 100.0*      5.03      5.28     152.5     268.9    4.1   65.8   19.4
2026-04-28     73.6  -74.4   13.21   13.60   61.9     52.5     75.1 100.0*      5.04      5.14     152.0     200.8    8.0   40.3   15.1
2026-04-29     73.7 -125.9   13.04   13.23   62.3     50.4     83.3 100.0*      5.07      5.16     152.1     208.0   12.4   24.0   15.6
2026-04-30     74.1   49.7   13.03   13.67   62.3     51.0     82.3 100.0*      5.04      5.32     150.8     205.9    9.5   64.3   20.4
2026-05-01     73.0   74.6   13.04   13.72   62.4     41.4    121.1 100.0*      5.03      5.34     151.0     325.2    4.6   62.3   18.4

* Buck% = average efficiency (power‑mean). Buck_min% / Buck_max% = daily min/max instantaneous efficiency (input power >0.1W).
* SoC% from ESP8266 Coulomb counting, anchored during sustained 14.2V, low net current. Asterisk (*) means no anchor that day.
* NetWh from ESP8266 (battery net energy).
* BME temperatures in °C.

🔧 MAINTENANCE / ENGINEERING EVENTS:
• 2026-03-09: HDC1000 → BME280 sensor replacement
• 2026-03-22: 16V 20F cap bank replacement + ina219 0x41 replacement
• 2026-03-23: System on bench power supply 11.38V steady for troubleshooting
• 2026-03-24 18:00: Battery disconnected for service
• 2026-03-25 19:21: Battery reconnected + ESP8266 battery monitor added (cap bank removed), ina41 sensor disconnected

📅 HARDWARE MILESTONES:
• 2025-10-23: 5Ah LiPo
• 2025-12-06: 20Ah LiPo
• 2026-02-04 18:33: 40W Solar Upgrade
• 2026-03-09 19:48: HDC1000 → BME280
```

## 5. Hardware Milestones

| Date       | Event                                                                 |
|------------|-----------------------------------------------------------------------|
| 2025-10-23 | 5 Ah LiPo battery installed                                          |
| 2025-12-06 | Upgraded to 20 Ah LiPo                                                |
| 2026-02-04 | 40 W solar panel upgrade                                              |
| 2026-03-09 | HDC1000 → BME280 replacement                                          |
| 2026-03-22 | 16 V 20 F cap bank replacement + INA219 (0x41) replacement (later disconnected) |
| 2026-03-23 | System on bench power supply (11.38 V) for troubleshooting            |
| 2026-03-24 | Battery disconnected for service                                      |
| 2026-03-25 | Battery reconnected + ESP8266 battery monitor added (cap bank removed) |

## 6. Recent Performance Sample

| Date       | PiWh | NetWh | BatVmin | BatVmax | Buck% | SoC% | USB5V_Vmin | USB5V_Vmax | USB5V_Imin | USB5V_Imax | Tmin | Tmax | Tavg |
|------------|------|-------|---------|---------|-------|------|------------|------------|------------|------------|------|------|------|
| 2026-04-07 | 75.1 | 3.7   | 13.20   | 14.78   | 61.5  | 97.0 | 5.04       | 5.26       | 152.1      | 341.1      | 4.8  | 60.4 | 20.2 |
| … (full daily table available in script output)                          |

> Asterisk (`*`) next to SoC% → no anchor found that day (cloudy / insufficient charge).

## 7. Key Lessons

- **Capacitor bank removal**: The 16 V 20 F cap bank interacted with the buck converter, likely causing high‑frequency oscillations. This resulted in increased battery current draw and elevated RMS noise on the INA41 sensor (floating input). After removal, current readings became stable.

- **Low‑voltage shutdown at 9.4 V** caused buck converter dropout (output ~4.3 V), trapping the Pi in a brownout loop. Upgrading to 20 Ah battery prevented deep discharge and solved the issue.

- **System‑level watchdog** was disabled because it caused unnecessary reboots. Service uses `Restart=always` without a watchdog.

- **Variable naming**: `current_ma` (ESP8266 net battery current) is ambiguous; would be clearer as `bat_current_ma`.

- **Data parsing**: Local LLMs choke on raw CSV megabytes; pre‑aggregation (as in `sensorbatterystatsjson.py`) is essential.

## 8. Health Monitoring Script (`./solarpi_health.sh`)

See Section 3 for the full script content and example output. It checks uptime, load, memory, storage, services (SSH, cron), BME280 sensor, WiFi RSSI, sensor socket, logs, battery, and recent kernel errors. Run regularly to verify system health.

---
**Document version**: Final – 2026-05-02
