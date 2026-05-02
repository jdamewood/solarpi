#!/usr/bin/env python3
from SDL_Pi_HDC1000 import SDL_Pi_HDC1000
import time

hdc1000 = SDL_Pi_HDC1000()

print("🔥 HDC1000 5-MINUTE HEATER RECOVERY TEST")
print("=========================================")

# Initial reading
print("\n📊 1. INITIAL (saturated):")
t1 = hdc1000.readTemperature()
rh1 = hdc1000.readHumidity()
print(f"Temp:   {t1:.1f}°C")
print(f"Humid:  {rh1:.1f}%")

# Heater ON for 5 MINUTES (300s)
print(f"\n🔥 2. HEATER ON FOR 5 MINUTES...")
print("⏳ This will take ~5:30 total...")
hdc1000.turnHeaterOn()
time.sleep(3000)  # 50 minutes

# Heater OFF + 30s settle
print("❄️  3. HEATER OFF + settling...")
hdc1000.turnHeaterOff()
time.sleep(30)

# Final reading
print("\n📊 4. AFTER 5-MIN HEATER:")
t2 = hdc1000.readTemperature()
rh2 = hdc1000.readHumidity()
print(f"Temp:   {t2:.1f}°C  (Δ{t2-t1:+.1f}°C)")
print(f"Humid:  {rh2:.1f}%  (Δ{rh2-rh1:+.1f}%)")

if rh2 < 95.0:
    print("✅ RECOVERED!")
elif rh2 >= 99.5:
    print("❌ STILL SATURATED - SENSOR DAMAGED")
else:
    print("⚠️  PARTIAL RECOVERY")

print("\n✅ Test complete!")

