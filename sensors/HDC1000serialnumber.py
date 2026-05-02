import smbus

I2C_ADDR = 0x40  # Default HDC1000 address

bus = smbus.SMBus(1)

# Read Manufacturer ID (0xFE)
bus.write_byte(I2C_ADDR, 0xFE)
manu_id = bus.read_word_data(I2C_ADDR, 0xFE)  # Should return 0x5449

# Read Device ID (0xFF)
bus.write_byte(I2C_ADDR, 0xFF)
device_id = bus.read_word_data(I2C_ADDR, 0xFF)  # Should return 0x1000

# Read Serial Number (0xFB, 0xFC, 0xFD)
def read_serial():
    # 0xFB: upper 2 bytes
    bus.write_byte(I2C_ADDR, 0xFB)
    sn_high = bus.read_word_data(I2C_ADDR, 0xFB)
    # 0xFC: middle 2 bytes
    bus.write_byte(I2C_ADDR, 0xFC)
    sn_mid = bus.read_word_data(I2C_ADDR, 0xFC)
    # 0xFD: lower byte (read as word, only use lower byte)
    bus.write_byte(I2C_ADDR, 0xFD)
    sn_low = bus.read_byte_data(I2C_ADDR, 0xFD)
    # Combine into 40-bit serial number
    serial = (sn_high << 24) | (sn_mid << 8) | sn_low
    return serial

serial_number = read_serial()
print(f"Manufacturer ID: {hex(manu_id)}")
print(f"Device ID: {hex(device_id)}")
print(f"Serial Number: {hex(serial_number)}")

