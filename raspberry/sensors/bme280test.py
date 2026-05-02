1#!/usr/bin/env python3
"""
SolarPi BME280 @ 0x76 - PRODUCTION READY
"""

import smbus2
import bme280
import time

bus = smbus2.SMBus(1)
address = 0x76

# Load calibration (uses your T1=28246, P1=37075)
calibration_params = bme280.load_calibration_params(bus, address)

print("🚀 SolarPi BME280 @ 0x76 - LIVE WEATHER")
print("Temp    | Pressure  | Humidity | Time")
print("-" * 42)

try:
    while True:
        data = bme280.sample(bus, address, calibration_params)
        print(f"{data.temperature:6.1f}°C | {data.pressure:9.1f} | {data.humidity:7.1f}% | {time.strftime('%H:%M:%S')}")
        time.sleep(1)
        
except KeyboardInterrupt:
    print("\n🛑 SolarPi weather stopped")

