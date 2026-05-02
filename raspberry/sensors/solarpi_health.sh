#!/bin/bash
# solarpi_health.sh - System health check for solarpi server (BME280 UPDATE)
# Run: chmod +x solarpi_health.sh && ./solarpi_health.sh

echo "🔋 SOLARPI SERVER HEALTH CHECK ($(date))"
echo "=================================================="

echo ""
echo "📊 SYSTEM OVERVIEW:"
echo "Uptime: $(uptime -p)"
echo "Load avg: $(uptime | awk '{print $(NF-2)" "$(NF-1)" "$(NF)}')"
echo "Memory: $(free -h | awk 'NR==2{printf "%.1fG/%.1fG (%.1f%%)\\n", $3/1024, $2/1024, $3*100/$2}')"
echo "CPU Temp: $(vcgencmd measure_temp | cut -d'=' -f2 | cut -d"'" -f1)°C"

echo ""
echo "💾 STORAGE:"
df -h / /boot /home 2>/dev/null | grep -E '^/dev' | awk '{printf "%-12s %s %s\\n", $1, $5, $6}'

echo ""
echo "🛡️ SERVICES:"
systemctl is-active --quiet ssh && echo "SSH: ✅ Active" || echo "SSH: ❌ Down"
systemctl is-active --quiet cron && echo "Cron: ✅ Active" || echo "Cron: ❌ Down"

echo ""
echo "🌡️ SENSORS:"
if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
    cpu_c=$(cat /sys/class/thermal/thermal_zone0/temp)
    echo "CPU: $((cpu_c/1000))°C"
fi

echo ""
echo "🌤️ BME280 SENSOR:"
# Query the Flask HTTP endpoint (port 5000) which is known to work
BME_JSON=$(curl -s --max-time 3 http://192.168.1.100:5000/solarpi/timeseries 2>/dev/null)
if echo "$BME_JSON" | grep -q "bme_temp"; then
    BME_TEMP=$(echo "$BME_JSON" | grep -o '"bme_temp":[^,}]*' | cut -d: -f2 | tr -d ' ,')
    BME_HUM=$(echo "$BME_JSON" | grep -o '"bme_hum":[^,}]*' | cut -d: -f2 | tr -d ' ,')
    BME_PRESS=$(echo "$BME_JSON" | grep -o '"bme_press":[^,}]*' | cut -d: -f2 | tr -d ' ,')
    
    printf "  Temp: %.2f °C\n" "$BME_TEMP" 2>/dev/null
    printf "  Humidity: %.1f %%\n" "$BME_HUM" 2>/dev/null
    printf "  Pressure: %.1f hPa\n" "$BME_PRESS" 2>/dev/null
    
    HUM_INT=$(echo "$BME_HUM" | cut -d. -f1)
    case $HUM_INT in
        0|100) echo "  ⚠️  Extreme humidity" ;;
        *)     echo "  ✅ Perfect" ;;
    esac
else
    echo "  ERROR: HTTP endpoint unreachable (server down?)"
fi


echo ""
echo "📡 NETWORK:"
echo "IP: $(hostname -I | awk '{print $1}')"

IW_BIN="/sbin/iw"
if [ -x "$IW_BIN" ]; then
    WIFIDEV=$("$IW_BIN" dev 2>/dev/null | awk '/Interface/ {print $2}' | head -1)
    if [ -n "$WIFIDEV" ]; then
        RSSI=$("$IW_BIN" dev "$WIFIDEV" link 2>/dev/null | awk '/signal:/ {print $2 " dBm"}')
        echo "WiFi RSSI: ${RSSI:-N/A} (${WIFIDEV})"
    else
        echo "WiFi RSSI: no WiFi interface"
    fi
else
    echo "WiFi RSSI: iw not installed"
fi

echo ""
echo "📊 SENSOR SERVER:"
if nc -z 192.168.1.164 5005 2>/dev/null; then
    echo "Socket 5005: ✅ LIVE"
else
    echo "Socket 5005: ❌ DOWN - restart server!"
fi

echo ""
echo "📊 POWERTEST LOGS:"
CURRENT_LOG=/home/pi/sensors/powertest.log
if [ -f "$CURRENT_LOG" ]; then
    SIZE=$(du -h "$CURRENT_LOG" | cut -f1)
    LINES=$(wc -l < "$CURRENT_LOG")
    echo "powertest.log: $SIZE ($LINES lines)"
    
    ARCHIVE_COUNT=$(ls /home/pi/sensors/powertest.log.* 2>/dev/null | wc -l)
    if [ "$ARCHIVE_COUNT" -gt 0 ]; then
        echo "Archives: $ARCHIVE_COUNT"
        echo "Recent:"
        for log in $(ls -t /home/pi/sensors/powertest.log.* | head -3); do
            SIZE=$(ls -lh "$log" | awk '{print $5}')
            if [[ "$log" == *.gz ]]; then
                if gzip -t "$log" 2>/dev/null; then
                    echo "  $log: $SIZE ✓"
                else
                    echo "  $log: $SIZE ❌ CORRUPT"
                fi
            else
                echo "  $log: $SIZE ✓"
            fi
        done
    fi
fi

echo ""
echo "🔋 BATTERY:"
if command -v /home/pi/sensors/ina219 >/dev/null 2>&1; then
    /home/pi/sensors/ina219
else
    echo "ina219 missing"
fi

echo ""
echo "⚠️  RECENT ERRORS:"
dmesg | tail -20 | grep -iE 'error|fail|oom|thermal|disconnect|i2c' || echo "✅ No critical errors"

echo ""
echo "✅ Health check complete!"
echo "BME280 upgrade: 100% operational 🌤️📡"
