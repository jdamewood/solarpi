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

**`sensorbatterystatsjson.py`**  

Fetches data from both Flask endpoints, computes daily statistics:

- Pi energy consumption (`PiWh`)
- Net battery energy (`NetWh`)
- Battery voltage min/max (`BatVmin` / `BatVmax`)
- Average buck efficiency (`Buck%`, ~62%)
- SoC from ESP8266 Coulomb counting (anchored at ≥14.2 V, low net current)
- USB5V rail voltage & current min/max
- BME280 temperature min/max/avg

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
