import socket
import json
import os
import time
from datetime import datetime

HOST = '192.168.1.164'
PORT = 5005

csv_header = [
    "timestamp",
    "ina45_v", "ina45_i", "ina41_v", "ina41_i", "ina44_v", "ina44_i",
    "tsl39_ch0", "tsl39_ch1", "tsl29_ch0", "tsl29_ch1",
    "tsl39_lux", "tsl29_lux",
    "hdc_temp", "hdc_hum", "wifi_rssi", "cpu_temp"
]

last_timestamp = None

def parse_timestamp(ts_str):
    try:
        return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"Timestamp parsing error: {e} for '{ts_str}'")
        return None

def check_timestamp(ts_str):
    global last_timestamp
    current_ts = parse_timestamp(ts_str)
    if current_ts is None:
        return False
    if last_timestamp is not None:
        if current_ts < last_timestamp:
            print(f"*** Timestamp mismatch: current {current_ts} < last {last_timestamp} ***")
            return False
        elif (current_ts - last_timestamp).total_seconds() > 3600:
            print(f"*** Timestamp jump detected: {current_ts} - {last_timestamp} ***")
    last_timestamp = current_ts
    return True

# Fields that should always be formatted as integers in CSV
int_fields = set([
    "tsl39_ch0", "tsl39_ch1", "tsl29_ch0", "tsl29_ch1","wifi_rssi"
])

# For current and voltage, temperature, humidity, lux etc. use float formatting
float_fields = set([
    "ina45_v", "ina45_i", "ina41_v", "ina41_i", "ina44_v", "ina44_i",
    "tsl39_lux", "tsl29_lux",
    "hdc_temp", "hdc_hum", "cpu_temp"
])

def format_value(col, val):
    if val in [None, "", "NULL"]:
        return ""
    if col in int_fields:
        try:
            return str(int(float(val)))
        except Exception:
            return ""
    if col in float_fields:
        try:
            return f"{float(val):.4f}"
        except Exception:
            return ""
    return str(val)

while True:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(15)
            s.connect((HOST, PORT))
            s.sendall(b'go')
            data_chunks = []
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data_chunks.append(chunk)
            data = b''.join(data_chunks)

        sensor_dict = json.loads(data.decode())

        if not check_timestamp(sensor_dict.get("timestamp", "")):
            print(f"Warning: Skipping entry due to timestamp issue: {sensor_dict.get('timestamp', '')}")
            continue

        # Write JSON log
        with open("sensor_log.json", "a") as jf:
            jf.write(json.dumps(sensor_dict) + "\n")

        # Format CSV line with appropriate formatting
        csv_line = ",".join(format_value(col, sensor_dict.get(col, "")) for col in csv_header)

        write_header = not os.path.exists("sensor_log.csv") or os.path.getsize("sensor_log.csv") == 0
        with open("sensor_log.csv", "a") as cf:
            if write_header:
                cf.write(",".join(csv_header) + "\n")
            cf.write(csv_line + "\n")

        print("Logged:", csv_line)

        time.sleep(15)

    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        continue
    except socket.timeout:
        print("Connection timeout")
        continue
    except Exception as e:
        print(f"Unexpected error: {e}")
        time.sleep(60)

