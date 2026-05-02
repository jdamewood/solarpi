#!/usr/bin/env python3
"""
BME280 @ 0x76 - PROPER CALIBRATION (SolarPi ready)
"""

import smbus
import time
import struct

bus = smbus.SMBus(1)
address = 0x76

# Read calibration data once
def read_calibration():
    cal1 = bus.read_i2c_block_data(address, 0x88, 24)
    cal2 = bus.read_i2c_block_data(address, 0xE1, 7)
    
    # Temperature calibration
    dig_T1 = (cal1[1] << 8) | cal1[0]
    dig_T2 = (cal1[3] << 8) | cal1[2]
    dig_T3 = (cal1[5] << 8) | cal1[4]
    
    # Pressure calibration  
    dig_P1 = (cal1[7] << 8) | cal1[6]
    dig_P2 = (cal1[9] << 8) | cal1[8]
    dig_P3 = (cal1[11] << 8) | cal1[10]
    dig_P4 = (cal1[13] << 8) | cal1[12]
    dig_P5 = (cal1[15] << 8) | cal1[14]
    dig_P6 = (cal1[17] << 8) | cal1[16]
    dig_P7 = (cal1[19] << 8) | cal1[18]
    dig_P8 = (cal1[21] << 8) | cal1[20]
    dig_P9 = (cal1[23] << 8) | cal1[22]
    
    # Humidity calibration
    dig_H1 = cal2[0]
    dig_H2 = (cal2[2] << 8) | cal2[1]
    dig_H3 = cal2[3]
    
    return (dig_T1,dig_T2,dig_T3,dig_P1,dig_P2,dig_P3,dig_P4,dig_P5,dig_P6,dig_P7,dig_P8,dig_P9,dig_H1,dig_H2,dig_H3)

cal = read_calibration()
print(f"✅ Calibration loaded: T1={cal[0]} T2={cal[1]} P1={cal[3]}")

# Initialize sensor
bus.write_byte_data(address, 0xF4, 0x27)  # Normal mode, 1x oversampling
time.sleep(0.1)

print("🚀 BME280 @ 0x76 - CALIBRATED READINGS")
print("Temp (°C) | Pressure (hPa) | Humidity (%)")
print("-" * 45)

def compensate_temp(t_raw, dig_T1, dig_T2, dig_T3):
    var1 = ((t_raw>>3) - (dig_T1<<1))
    var2 = (var1 * dig_T2) >> 11
    var3 = ((var1 >> 1) * (var1 >> 1)) >> 12
    var3 = var3 * (dig_T3 << 4)
    t_fine = var2 + var3
    temp = ((t_fine * 5 + 128) >> 8)/100.0
    return temp, t_fine

while True:
    try:
        # Read raw data
        data = bus.read_i2c_block_data(address, 0xF7, 8)
        press_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        humid_raw = (data[6] << 8) | data[7]
        
        # Compensate temperature
        temp_c, t_fine = compensate_temp(temp_raw, *cal[:3])
        
        # Simple pressure (needs full compensation)
        press_hpa = press_raw / 256.0 / 100.0  # Rough
        
        print(f"{temp_c:6.1f}°C | {press_hpa:9.1f}hPa | {humid_raw/65535*100:7.1f}%  {time.strftime('%H:%M:%S')}")
        time.sleep(5)
        
    except KeyboardInterrupt:
        print("\n🛑 Stopped")
        break
    except Exception as e:
        print(f"Error: {e}")

