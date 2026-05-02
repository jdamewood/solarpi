import socket
import time
import json
import subprocess
import re
import board
import busio
import adafruit_tsl2561
from adafruit_ina219 import INA219
from SDL_Pi_HDC1000 import SDL_Pi_HDC1000
from math import isnan

# --- INA219 SETUP ---
i2c_bus = busio.I2C(board.SCL, board.SDA)
ina_addresses = [0x45, 0x41, 0x44]
ina_sensors = [INA219(i2c_bus, addr) for addr in ina_addresses]

# --- TSL2561 SETUP ---
tsl_addresses = [0x39, 0x29]
tsl_sensors = [adafruit_tsl2561.TSL2561(i2c_bus, address=addr) for addr in tsl_addresses]

# Enable auto gain and start with max integration time
for tsl in tsl_sensors:
    tsl.enabled = True
    tsl.enable_auto_range = True  # auto gain switching (experimental feature)
    tsl.integration_time = 2  # 402 ms integration time for max sensitivity

# ---- HDC10000 SETUP ----
hdc = SDL_Pi_HDC1000()

def read_ina219_all():
    readings = []
    for sensor in ina_sensors:
        voltage = sensor.bus_voltage
        current = sensor.current
        readings.append((voltage, current))
    return readings

def read_tsl2561_all():
    readings = []
    for tsl in tsl_sensors:
        # Raw channel readings
        broadband = tsl.broadband  # integer
        infrared = tsl.infrared    # integer

        # Calculated lux value (float or None)
        lux = tsl.lux

        readings.append((broadband, infrared, lux))
    return readings


def read_hdc1000():
    temp = hdc.readTemperature()
    humidity = hdc.readHumidity()
    return temp, humidity

def get_wifi_rssi(interface='wlan0'):
    try:
        output = subprocess.check_output(['iwconfig', interface]).decode()
        match = re.search(r'Signal level=(-?\d+) dBm', output)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return None

def get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp_str = f.readline()
            return float(temp_str) / 1000.0
    except Exception:
        return None

def read_tsl2561_all():
    lux_values = []
    for tsl in tsl_sensors:
        lux = tsl.lux
        if lux is None:  # out of range or invalid data
            lux_values.append(float('nan'))  # or None if preferred
        else:
            lux_values.append(lux)
    return lux_values

def get_sensor_line():
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    ina_readings = read_ina219_all()
    tsl_readings = read_tsl2561_all()
    temp, humidity = read_hdc1000()
    wifi_rssi = get_wifi_rssi()
    cpu_temp = get_cpu_temp()

    line = (
        f"{now}, "
        + ", ".join([f"INA219_{hex(ina_addresses[i])}: {v:.3f}V {c:.1f}mA" for i, (v, c) in enumerate(ina_readings)])
        + ", "
        + ", ".join([
            f"TSL2561_{hex(tsl_addresses[i])}: Raw_BW={bw} Raw_IR={ir} Lux={lux:.2f}" 
            if lux is not None else
            f"TSL2561_{hex(tsl_addresses[i])}: Raw_BW={bw} Raw_IR={ir} Lux=NULL"
            for i, (bw, ir, lux) in enumerate(tsl_readings)
        ])
        + f", HDC1000: {temp:.2f}C {humidity:.2f}%, "
        + f"WiFi RSSI: {wifi_rssi if wifi_rssi is not None else 'N/A'} dBm, "
        + f"CPU Temp: {cpu_temp:.2f}C"
    )
    return line

# --- TCP Server ---
HOST = ''      # Listen on all interfaces
PORT = 5005    # Arbitrary non-privileged port

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen(1)
    print(f"Sensor server listening on port {PORT}...")
    while True:
        conn, addr = s.accept()
        with conn:
            print('Connected by', addr)
            command = conn.recv(1024).decode()
            if command.strip().lower() == 'go':
                line = get_sensor_line()
                conn.sendall(line.encode())
                print("Sent:", line)
            else:
                conn.sendall(b'invalid request')

