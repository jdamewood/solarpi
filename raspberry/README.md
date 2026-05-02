
# Files in `raspberry/sensors/`

| File                         | Description |
|------------------------------|-------------|
| `adafruit_TSL2651test.py`    | Test script for TSL2561 light sensor |
| `bme280_manual.py`       | Reads BME280 temperature, pressure, and humidity using manual calibration formulas (floating‑point). TODO instructions for BME280 raspberry kernal driver install|
| `bme280test.py`              | TODO: add description |
| `HDC1000.py`                 | TODO: add description |
| `HDC1000serialnumber.py`     | TODO: add description |
| `ina219`                     | Compiled binary to read INA219 power rail (usage: `ina219 0x44` or `0x45`) |
| `ina219.c`                   | Source code for `ina219` binary |
| `ina219test.py`              | Python version to read INA219 sensor |
| `power.py`                   | TODO: add description |
| `powertest_server_json.py`   | Flask server for SolarPi (provides `/solarpi/timeseries` and `/esp8266` endpoints) |
| `powertest_server.py`        | Older version of the server (may be deprecated) |
| `SDL_Pi_HDC1000.py`          | Library for HDC1000 temperature/humidity sensor |
| `sensorserver.py`            | TODO: add description |
| `solarpi_health.sh`          | System health check script (uptime, BME280, WiFi, logs, etc.) |
| `test_hdc1000.py`            | Test script for HDC1000 sensor |
| `testina219.c`               | Test program for INA219 (C source) |
| `TSL2561test.py`             | Test script for TSL2561 light sensor |

> **Note**: The `LICENSE` (MIT) and `README.md` are located in the repository root, not inside this folder.
