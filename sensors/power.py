#!/usr/bin/env python
# Based from Chris B https://github.com/chrisb2/pi_ina219 Added time 
# stamp,gain setting and i2c addressing
 
from ina219 import INA219 
from ina219 import DeviceRangeError 
import time 
SHUNT_OHMS = 0.1 
MAX_EXPECTED_AMPS = 0.2 
def read():
    ina = INA219(SHUNT_OHMS, MAX_EXPECTED_AMPS, address=0x45)
    ina.configure(ina.RANGE_16V, ina.GAIN_AUTO)
# Output data to screen
#  print (time.strftime("%d/%m/%Y")),(time.strftime("%H:%M:%S")),",",
    print(time.strftime("%m/%d/%Y")),(time.strftime("%H:%M:%S")),",","BusVoltage: %.3f V" % ina.voltage(),",",
    try:
        print "Bus Current: %.3f mA" % ina.current(),",",
        print "Power: %.3f mW" % ina.power(),",",
        print "Shunt voltage: %.3f mV" % ina.shunt_voltage(),
    except DeviceRangeError as e:
        print "Current overflow" 
if __name__ == "__main__":
    read()
