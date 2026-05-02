# SDL_Pi_HDC1000

# Raspberry Pi Driver for the SwitchDoc Labs HDC1000 Breakout Board

# SwitchDoc Labs
# January 2017
# Version 1.1

# Constants
HDC1000_ADDRESS = 0x40  # 1000000

# Registers
HDC1000_TEMPERATURE_REGISTER = 0x00
HDC1000_HUMIDITY_REGISTER = 0x01
HDC1000_CONFIGURATION_REGISTER = 0x02
HDC1000_MANUFACTURERID_REGISTER = 0xFE
HDC1000_DEVICEID_REGISTER = 0xFF
HDC1000_SERIALIDHIGH_REGISTER = 0xFB
HDC1000_SERIALIDMID_REGISTER = 0xFC
HDC1000_SERIALIDBOTTOM_REGISTER = 0xFD

# Configuration Register Bits
HDC1000_CONFIG_RESET_BIT = 0x8000
HDC1000_CONFIG_HEATER_ENABLE = 0x2000
HDC1000_CONFIG_ACQUISITION_MODE = 0x1000
HDC1000_CONFIG_BATTERY_STATUS = 0x0800
HDC1000_CONFIG_TEMPERATURE_RESOLUTION = 0x0400
HDC1000_CONFIG_HUMIDITY_RESOLUTION_HBIT = 0x0200
HDC1000_CONFIG_HUMIDITY_RESOLUTION_LBIT = 0x0100
HDC1000_CONFIG_TEMPERATURE_RESOLUTION_14BIT = 0x0000
HDC1000_CONFIG_TEMPERATURE_RESOLUTION_11BIT = 0x0400
HDC1000_CONFIG_HUMIDITY_RESOLUTION_14BIT = 0x0000
HDC1000_CONFIG_HUMIDITY_RESOLUTION_11BIT = 0x0100
HDC1000_CONFIG_HUMIDITY_RESOLUTION_8BIT = 0x0200

I2C_SLAVE = 0x0703

import struct
import array
import time
import io
import fcntl

HDC1000_fw = 0
HDC1000_fr = 0

class SDL_Pi_HDC1000:

    def __init__(self, twi=1, addr=HDC1000_ADDRESS):
        global HDC1000_fr, HDC1000_fw

        HDC1000_fr = io.open("/dev/i2c-" + str(twi), "rb", buffering=0)
        HDC1000_fw = io.open("/dev/i2c-" + str(twi), "wb", buffering=0)

        # set device address
        fcntl.ioctl(HDC1000_fr, I2C_SLAVE, addr)
        fcntl.ioctl(HDC1000_fw, I2C_SLAVE, addr)

        time.sleep(0.015)  # 15ms startup time

        config = HDC1000_CONFIG_ACQUISITION_MODE
        s = [HDC1000_CONFIGURATION_REGISTER, config >> 8, 0x00]
        s2 = bytearray(s)
        HDC1000_fw.write(s2)  # sending config register bytes
        time.sleep(0.015)  # From the data sheet

    def readTemperature(self):
        s = [HDC1000_TEMPERATURE_REGISTER]  # temp
        s2 = bytearray(s)
        HDC1000_fw.write(s2)
        time.sleep(0.0625)  # From the data sheet

        data = HDC1000_fr.read(2)  # read 2 byte temperature data
        buf = array.array('B', data)

        # Convert the data
        temp = (buf[0] * 256) + buf[1]
        cTemp = (temp / 65536.0) * 165.0 - 40
        return cTemp

    def readHumidity(self):
        time.sleep(0.015)  # From the data sheet
        s = [HDC1000_HUMIDITY_REGISTER]  # hum
        s2 = bytearray(s)
        HDC1000_fw.write(s2)
        time.sleep(0.0625)  # From the data sheet

        data = HDC1000_fr.read(2)  # read 2 byte humidity data
        buf = array.array('B', data)

        humidity = (buf[0] * 256) + buf[1]
        humidity = (humidity / 65536.0) * 100.0
        return humidity

    def readConfigRegister(self):
        s = [HDC1000_CONFIGURATION_REGISTER]
        s2 = bytearray(s)
        HDC1000_fw.write(s2)
        time.sleep(0.0625)
        data = HDC1000_fr.read(2)
        buf = array.array('B', data)
        return buf[0] * 256 + buf[1]

    def turnHeaterOn(self):
        config = self.readConfigRegister()
        config = config | HDC1000_CONFIG_HEATER_ENABLE
        s = [HDC1000_CONFIGURATION_REGISTER, config >> 8, 0x00]
        s2 = bytearray(s)
        HDC1000_fw.write(s2)
        time.sleep(0.015)
        return

    def turnHeaterOff(self):
        config = self.readConfigRegister()
        config = config & ~HDC1000_CONFIG_HEATER_ENABLE
        s = [HDC1000_CONFIGURATION_REGISTER, config >> 8, 0x00]
        s2 = bytearray(s)
        HDC1000_fw.write(s2)
        time.sleep(0.015)
        return

    def setHumidityResolution(self, resolution):
        config = self.readConfigRegister()
        config = (config & ~0x0300) | resolution
        s = [HDC1000_CONFIGURATION_REGISTER, config >> 8, 0x00]
        s2 = bytearray(s)
        HDC1000_fw.write(s2)
        time.sleep(0.015)
        return

    def setTemperatureResolution(self, resolution):
        config = self.readConfigRegister()
        config = (config & ~0x0400) | resolution
        s = [HDC1000_CONFIGURATION_REGISTER, config >> 8, 0x00]
        s2 = bytearray(s)
        HDC1000_fw.write(s2)
        time.sleep(0.015)
        return

    def readBatteryStatus(self):
        config = self.readConfigRegister()
        config = config & ~HDC1000_CONFIG_HEATER_ENABLE
        if config == 0:
            return True
        else:
            return False

    def readManufacturerID(self):
        s = [HDC1000_MANUFACTURERID_REGISTER]
        s2 = bytearray(s)
        HDC1000_fw.write(s2)
        time.sleep(0.0625)
        data = HDC1000_fr.read(2)
        buf = array.array('B', data)
        return buf[0] * 256 + buf[1]

    def readDeviceID(self):
        s = [HDC1000_DEVICEID_REGISTER]
        s2 = bytearray(s)
        HDC1000_fw.write(s2)
        time.sleep(0.0625)
        data = HDC1000_fr.read(2)
        buf = array.array('B', data)
        return buf[0] * 256 + buf[1]

    def readSerialNumber(self):
        serialNumber = 0
        s = [HDC1000_SERIALIDHIGH_REGISTER]
        s2 = bytearray(s)
        HDC1000_fw.write(s2)
        time.sleep(0.0625)
        data = HDC1000_fr.read(2)
        buf = array.array('B', data)
        serialNumber = buf[0] * 256 + buf[1]

        s = [HDC1000_SERIALIDMID_REGISTER]
        s2 = bytearray(s)
        HDC1000_fw.write(s2)
        time.sleep(0.0625)
        data = HDC1000_fr.read(2)
        buf = array.array('B', data)
        serialNumber = serialNumber * 256 + buf[0] * 256 + buf[1]

        s = [HDC1000_SERIALIDBOTTOM_REGISTER]
        s2 = bytearray(s)
        HDC1000_fw.write(s2)
        time.sleep(0.0625)
        data = HDC1000_fr.read(2)
        buf = array.array('B', data)
        serialNumber = serialNumber * 256 + buf[0] * 256 + buf[1]

        return serialNumber

