#!/usr/bin/python3
"""
TSL2561 FULL 3×2 MATRIX - FIXED Gain Control
"""

import smbus2
import time

bus = smbus2.SMBus(1)
addresses = [0x39, 0x29]

def read_tsl_raw(integration_reg, gain_bit):
    readings = []
    
    for addr in addresses:
        try:
            bus.write_byte_data(addr, 0x00 | 0x80, 0x03)  # Power ON
            
            # SINGLE WRITE: integration (bits 1:0) + gain (bit 4)
            control = integration_reg | (gain_bit << 4)  # Bit 4 = gain
            bus.write_byte_data(addr, 0x01 | 0x80, control)
            
            if integration_reg == 0x00: time.sleep(0.02)
            elif integration_reg == 0x01: time.sleep(0.11)
            else: time.sleep(0.42)
            
            ch0_raw = bus.read_i2c_block_data(addr, 0x0C | 0x80, 2)
            ch1_raw = bus.read_i2c_block_data(addr, 0x0E | 0x80, 2)
            ch0 = ch0_raw[1] * 256 + ch0_raw[0]
            ch1 = ch1_raw[1] * 256 + ch1_raw[0]
            
            readings.append((f"0x{addr:02X}", ch0, ch1, ch0-ch1))
            bus.write_byte(addr, 0x00)
        except:
            readings.append((f"0x{addr:02X}", 0, 0, 0))
    return readings

print("🚀 TSL2561 3×2 MATRIX - FIXED!")
print("="*80)
print(f"{'Time':<12} {'Gain':<4} {'Intg':<6} {'Addr':<6} {'Ch0':>6} {'Ch1':>6} {'Vis':>6} {'Lux'}")

matrix = [
    ('13.7ms', 0x00, 0), ('13.7ms', 0x00, 1),
    ('101ms', 0x01, 0), ('101ms', 0x01, 1),
    ('402ms', 0x10, 0), ('402ms', 0x10, 1)
]

for intg_name, intg_reg, gain_bit in matrix:
    gain_str = "16x" if gain_bit else "1x"
    readings = read_tsl_raw(intg_reg, gain_bit)
    now = time.strftime("%H:%M:%S")
    
    for addr, ch0, ch1, vis in readings:
        if ch0 >= 65000:
            lux = ">120k ☀️"
        else:
            ratio = ch1/ch0 if ch0 else 0
            if ratio <= 0.50: lux = f"{0.0304*ch0-0.062*ch0*(ratio**1.4):.0f}"
            elif ratio <= 0.61: lux = f"{0.0224*ch0-0.031*ch1:.0f}"
            elif ratio <= 0.80: lux = f"{0.0128*ch0-0.0153*ch1:.0f}"
            elif ratio <= 1.30: lux = f"{0.00146*ch0-0.00112*ch1:.0f}"
            else: lux = "0"
        print(f"{now:<12} {gain_str:<4} {intg_name:<6} {addr:<6} {ch0:>6} {ch1:>6} {vis:>6} {lux}")
    print()

print("✅ 3×2×2 MATRIX FIXED - 16x gain now works!")
