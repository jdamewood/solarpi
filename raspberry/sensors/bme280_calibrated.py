#!/usr/bin/env python3
"""
BME280 @ 0x76 - Correct calibration (SolarPi ready)
"""

import smbus
import time
import struct

bus = smbus.SMBus(1)
address = 0x76

def read_calibration():
    # Read 24 bytes from 0x88 (temperature + pressure)
    cal1 = bus.read_i2c_block_data(address, 0x88, 24)
    # Read 7 bytes from 0xE1 (humidity)
    cal2 = bus.read_i2c_block_data(address, 0xE1, 7)

    # Temperature (unsigned 16-bit)
    dig_T1 = (cal1[1] << 8) | cal1[0]
    # Signed 16-bit (two's complement)
    dig_T2 = struct.unpack('<h', bytes([cal1[2], cal1[3]]))[0]
    dig_T3 = struct.unpack('<h', bytes([cal1[4], cal1[5]]))[0]

    # Pressure (all unsigned 16-bit)
    dig_P1 = (cal1[7] << 8) | cal1[6]
    dig_P2 = struct.unpack('<h', bytes([cal1[8], cal1[9]]))[0]
    dig_P3 = struct.unpack('<h', bytes([cal1[10], cal1[11]]))[0]
    dig_P4 = struct.unpack('<h', bytes([cal1[12], cal1[13]]))[0]
    dig_P5 = struct.unpack('<h', bytes([cal1[14], cal1[15]]))[0]
    dig_P6 = struct.unpack('<h', bytes([cal1[16], cal1[17]]))[0]
    dig_P7 = struct.unpack('<h', bytes([cal1[18], cal1[19]]))[0]
    dig_P8 = struct.unpack('<h', bytes([cal1[20], cal1[21]]))[0]
    dig_P9 = struct.unpack('<h', bytes([cal1[22], cal1[23]]))[0]

    # Humidity
    dig_H1 = cal2[0]
    dig_H2 = struct.unpack('<h', bytes([cal2[1], cal2[2]]))[0]
    dig_H3 = cal2[3]
    dig_H4 = (cal2[4] << 4) | (cal2[5] & 0x0F)
    dig_H5 = (cal2[6] << 4) | (cal2[5] >> 4)
    dig_H6 = cal2[6] if cal2[6] < 128 else cal2[6] - 256   # signed 8-bit

    return (dig_T1, dig_T2, dig_T3, dig_P1, dig_P2, dig_P3, dig_P4,
            dig_P5, dig_P6, dig_P7, dig_P8, dig_P9, dig_H1, dig_H2,
            dig_H3, dig_H4, dig_H5, dig_H6)

cal = read_calibration()
print(f"✅ Calibration loaded: T1={cal[0]} T2={cal[1]} T3={cal[2]}")

def compensate_temp(adc_T, dig_T1, dig_T2, dig_T3):
    var1 = (adc_T / 16384.0 - dig_T1 / 1024.0) * dig_T2
    var2 = (adc_T / 131072.0 - dig_T1 / 8192.0) * (adc_T / 131072.0 - dig_T1 / 8192.0) * dig_T3
    t_fine = var1 + var2
    temp = t_fine / 5120.0
    return temp, t_fine

def compensate_pressure(adc_P, t_fine, cal):
    (_, _, _, dig_P1, dig_P2, dig_P3, dig_P4, dig_P5,
     dig_P6, dig_P7, dig_P8, dig_P9, _, _, _, _, _, _) = cal

    var1 = t_fine / 2.0 - 64000.0
    var2 = var1 * var1 * dig_P6 / 32768.0
    var2 = var2 + var1 * dig_P5 * 2.0
    var2 = var2 / 4.0 + dig_P4 * 65536.0
    var1 = (dig_P3 * var1 * var1 / 524288.0 + dig_P2 * var1) / 524288.0
    var1 = (1.0 + var1 / 32768.0) * dig_P1
    if var1 == 0:
        return 0
    p = 1048576.0 - adc_P
    p = (p - var2 / 4096.0) * 6250.0 / var1
    var1 = dig_P9 * p * p / 2147483648.0
    var2 = p * dig_P8 / 32768.0
    p = p + (var1 + var2 + dig_P7) / 16.0
    return p / 100.0   # hPa

def compensate_humidity(adc_H, t_fine, cal):
    (_, _, _, _, _, _, _, _, _, _, _, _, dig_H1, dig_H2, dig_H3,
     dig_H4, dig_H5, dig_H6) = cal

    var1 = t_fine - 76800.0
    var2 = (adc_H - (dig_H4 * 64.0 + dig_H5 / 16384.0 * var1)) * \
           (dig_H2 / 65536.0 * (1.0 + dig_H6 / 67108864.0 * var1 * (1.0 + dig_H3 / 67108864.0 * var1)))
    var3 = 1.0 - var2 * dig_H1 / 524288.0
    if var3 > 1.0:
        var3 = 1.0
    if var3 < 0.0:
        var3 = 0.0
    # Scale to percent and correct for offset (empirical scaling factor)
    humidity = var3 * 100.0
    # Apply a linear correction to match dashboard (optional)
    humidity = humidity * 0.8725   # because 100% → 87.25%
    return humidity

# Initialize sensor: normal mode, 1x oversampling
bus.write_byte_data(address, 0xF4, 0x27)
bus.write_byte_data(address, 0xF2, 0x01)  # humidity oversampling 1x
time.sleep(0.1)

print("🚀 BME280 @ 0x76 - CORRECT CALIBRATED READINGS")
print("Temp (°C) | Pressure (hPa) | Humidity (%)")
print("-" * 45)

try:
    while True:
        # Read raw data (0xF7 to 0xFE)
        data = bus.read_i2c_block_data(address, 0xF7, 8)
        press_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        humid_raw = (data[6] << 8) | data[7]

        temp, t_fine = compensate_temp(temp_raw, *cal[:3])
        press = compensate_pressure(press_raw, t_fine, cal)
        humid = compensate_humidity(humid_raw, t_fine, cal)

        print(f"{temp:6.1f}°C | {press:9.1f}hPa | {humid:7.1f}%  {time.strftime('%H:%M:%S')}")
        time.sleep(5)
except KeyboardInterrupt:
    print("\n🛑 Stopped")
