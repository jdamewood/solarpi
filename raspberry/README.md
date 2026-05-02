# Files in `raspberry/sensors/`

| File                         | Description |
|------------------------------|-------------|
| `adafruit_TSL2651test.py`    | Test script for TSL2561 light sensor (filename typo). Reads chip ID, gain, integration time, and lux. |
| `bme280_manual.py`           | Reads BME280 temperature, pressure, and humidity using manual calibration formulas (floating‑point). (TODO: add instructions for Raspberry Pi kernel driver alternative.) |
| `bme280kerneltest.py`        | Uses the `bme280` Python library (I²C, userspace) for readings. Often more accurate than manual method. |
| `HDC1000.py`                 | Reads HDC1000 temperature/humidity sensor. Removed from system due to poor performance (becomes 100% saturated even with heater bit toggled). |
| `HDC1000serialnumber.py`     | Reads the unique serial number from an HDC1000 sensor (for identification). |
| `ina219`                     | Compiled C binary to read INA219 at a given I²C address (usage: `ina219 0x44` or `0x45`). Displays bus voltage, current, power. |
| `ina219.c`                   | Source code for the `ina219` binary. |
| `ina219test.py`              | Python alternative to read INA219 sensor (useful for debugging). |
| `power.py`                   |  Legacy Python 2 script to read INA219 at address 0x45. Not currently used; would need updating to Python 3 for modern systems  (deprecated). |
| `powertest_server_json.py`   | Main sensor server on Raspberry Pi. Reads INA219, TSL2561, and BME280 at 1 Hz, logs to CSV/JSON, listens on port 5005 for `"go"` command (returns JSON). Used by `solarpi_health.sh` and client dashboards. |
| `powertest_server.py`        | Older version of the server (deprecated). |
| `SDL_Pi_HDC1000.py`          | Third‑party library for HDC1000 sensor. |
| `sensorserver.py`            | Simple socket server that streams sensor data (pre‑Flask implementation). Possibly deprecated. |
| `solarpi_health.sh`          | Comprehensive system health check. Reads BME280 via port 5005 socket, displays uptime, load, memory, CPU temp, storage, services (SSH, cron), WiFi RSSI, log sizes, battery (via `ina219`), and recent kernel errors. |
| `test_hdc1000.py`            | Quick test for HDC1000 sensor. |
| `testina219.c`               | Minimal C test for INA219 (different from the full `ina219.c`). |
| `TSL2561test.py`             | Alternative test script for TSL2561 light sensor (may use different settings). |

> **Note**: The `LICENSE` (MIT) and `README.md` are located in the repository root, not inside this folder.
