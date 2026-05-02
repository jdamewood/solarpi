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
```
## Enable and Start the Service
```
# Enable auto-start on boot
sudo systemctl enable powertest.service

# Start the service now
sudo systemctl start powertest.service
```
## Check Status
```bash
sudo systemctl status powertest.service
```
Expected output: ```active (running)```.

## View Logs
```bash
journalctl -u powertest.service -f
```
## Press ```Ctrl+C``` to exit.
## Restart or Reload After Changes
If you edit the service file, run:

```bash
sudo systemctl daemon-reload
sudo systemctl restart powertest.service
```
## Stop and Disable (if needed)
```bash
sudo systemctl stop powertest.service
sudo systemctl disable powertest.service
```
## Notes
- The service uses Restart=always – the script will be restarted automatically if it crashes.
- Ensure Python dependencies (adafruit‑ina219, smbus2, bme280) are installed in the system or user environment.
- The working directory /home/pi/sensors must contain powertest_server_json.py and the sensor libraries.


Then, in your `README.md`, you can reference this file with a simple link:

```markdown
For details on setting up the sensor server as a systemd service (auto‑start on boot, status checks, logs), see [systemd_setup.md](systemd_setup.md).
This keeps the main documentation tidy while providing complete instructions.

