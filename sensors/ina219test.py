import time
import subprocess
import os
import statistics
import re
from adafruit_ina219 import INA219
import board
import busio

# Configuration - FIXED for 0x44 (13V input rail)
I2C_ADDRESS = 0x44      # 13V → MPPT → Pi5 USB
SAMPLES = 50            # Fewer samples, faster test
ERROR_THRESHOLD_PCT = 2.0  # Tight: ±2mA at 100mA
SAMPLE_INTERVAL = 1.0

# Setup with explicit calibration for 0.1Ω shunt, 32V/3.2A
i2c_bus = busio.I2C(board.SCL, board.SDA)
ina = INA219(i2c_bus, I2C_ADDRESS)
ina._cal_value = 4096   # Match standard C implementation

print(f"Testing 0x{I2C_ADDRESS:x} (13V input rail)")
print(f"Python LSB: {ina._current_lsb:.1f}μA/bit")

exe_path = os.path.join(os.path.dirname(__file__), "ina219")
print("\nBaseline C reading:")
result = subprocess.run([exe_path, f"0x{I2C_ADDRESS:x}"], capture_output=True, text=True)
print(result.stdout)

print("\nSample,Python(mA),C(mA),Error(mA),Error(%)")
print("-" * 50)

errors, py_currents, c_currents = [], [], []

for i in range(1, SAMPLES + 1):
    # Python reading
    try:
        py_current = ina.current
    except Exception as e:
        print(f"{i:2d}: Python error: {e}")
        continue

    # C reading with settle time
    time.sleep(0.1)
    result = subprocess.run([exe_path, f"0x{I2C_ADDRESS:x}"], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"{i:2d}: C failed")
        continue
        
    # Robust parsing
    match = re.search(r'Current:\s*([\d.]+)\s*mA', result.stdout.strip())
    if not match:
        print(f"{i:2d}: Parse failed")
        continue
    c_current = float(match.group(1))
    
    error = py_current - c_current
    error_pct = (error / py_current * 100) if py_current > 10 else 0
    
    errors.append(error); py_currents.append(py_current); c_currents.append(c_current)
    
    print(f"{i:2d}, {py_current:6.1f}, {c_current:6.1f}, {error:6.1f}, {error_pct:5.1f}%")
    if abs(error_pct) > ERROR_THRESHOLD_PCT:
        print(f"  ⚠️  {error_pct:+.1f}% ERROR")

    time.sleep(SAMPLE_INTERVAL)

# Results summary
if errors:
    print("\n" + "="*60)
    print("VALIDATION RESULTS (0x44: 13V INPUT RAIL)")
    print(f"Samples:  {len(errors)}")
    mean_py = statistics.mean(py_currents)
    print(f"Python avg:  {mean_py:6.1f}mA")
    print(f"C avg:       {statistics.mean(c_currents):6.1f}mA") 
    print(f"Mean error:  {statistics.mean(errors):+6.1f}mA ({statistics.mean(errors)/mean_py*100:+.2f}%)")
    print(f"Max error:   {max(errors):+6.1f}mA ({max(errors)/mean_py*100:+.1f}%)")
    print(f"Stddev:      {statistics.stdev(errors):5.1f}mA")
