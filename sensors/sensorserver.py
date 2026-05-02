import socket
import time
import subprocess
import re

# --- Sensor imports (replace with your actual sensor libraries) ---
# from adafruit_ina219 import INA219
# import board
# import busio
# import smbus
# from SDL_Pi_HDC1000 import SDL_Pi_HDC1000

# --- Placeholder sensor read functions for demonstration ---
def read_ina219_all():
    # Replace with actual INA219 readings
    return [
        (5.112, 191.2),  # (voltage, current) for 0x45
        (11.436, 116.4), # for 0x41
        (11.376, 125.5)  # for 0x44
    ]

def read_tsl2561_all():
    # Replace with actual TSL2561 readings
    return [
        (20, 4),  # (CH0, CH1) for 0x39
        (26, 5)   # for 0x29
    ]

def read_hdc1000():
    # Replace with actual HDC1000 readings
    return 21.82, 97.58  # (temp, humidity)

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

def get_sensor_line():
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    ina_addresses = [0x45, 0x41, 0x44]
    tsl_addresses = [0x39, 0x29]

    ina_readings = read_ina219_all()
    tsl_readings = read_tsl2561_all()
    temp, humidity = read_hdc1000()
    wifi_rssi = get_wifi_rssi()
    cpu_temp = get_cpu_temp()

    line = (
        f"{now}, "
        + ", ".join([f"INA219_{hex(ina_addresses[i])}: {v:.3f}V {c:.1f}mA" for i, (v, c) in enumerate(ina_readings)])
        + ", "
        + ", ".join([f"TSL2561_{hex(tsl_addresses[i])}: CH0={ch0} CH1={ch1}" for i, (ch0, ch1) in enumerate(tsl_readings)])
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

