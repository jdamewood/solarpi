# Systemd Setup for SolarPi Sensor Server

## Service File: `powertest.service`

Create the service file at `/etc/systemd/system/powertest.service`:

```ini
[Unit]
Description=SolarPi PowerTest Sensor Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/sensors
ExecStart=/usr/bin/python3 /home/pi/sensors/powertest_server_json.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
