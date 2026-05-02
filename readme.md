# SolarPi – Solar‑Powered Raspberry Pi Monitoring System

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
