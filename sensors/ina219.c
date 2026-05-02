#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wiringPiI2C.h>
#include <unistd.h>
#include <stdint.h>

#define REG_CALIBRATION 0x05
#define REG_CONFIG 0x00
#define REG_BUS_VOLTAGE 0x02
#define REG_POWER 0x03
#define REG_CURRENT 0x04

#define SHUNT_RESISTOR_OHMS 0.1       // Shunt resistor value
#define MAX_EXPECTED_CURRENT 3.2      // Max expected current in Amps

uint16_t swap_bytes(uint16_t val) {
    return (val << 8) | (val >> 8);
}

void configure_ina219(int fd) {
    float current_lsb = MAX_EXPECTED_CURRENT / 32768.0f;
    int calibration = (int)(0.04096 / (current_lsb * SHUNT_RESISTOR_OHMS));
    wiringPiI2CWriteReg16(fd, REG_CALIBRATION, swap_bytes(calibration));
    
    int config = 0x399F;  // 12-bit, continuous
    wiringPiI2CWriteReg16(fd, REG_CONFIG, swap_bytes(config));
}

int16_t read_current(int fd) {
    uint16_t raw = wiringPiI2CReadReg16(fd, REG_CURRENT);
    return (int16_t)swap_bytes(raw);
}

uint16_t read_bus_voltage(int fd) {
    uint16_t raw = wiringPiI2CReadReg16(fd, REG_BUS_VOLTAGE);
    return swap_bytes(raw);
}

uint16_t read_power(int fd) {
    uint16_t raw = wiringPiI2CReadReg16(fd, REG_POWER);
    return swap_bytes(raw);
}

int main(int argc, char *argv[]) {
    if (argc != 2) {
        printf("Usage: %s <I2C_ADDRESS>  (0x44 or 0x45)\n", argv[0]);
        return 1;
    }

    // Parse hex address
    int addr;
    if (sscanf(argv[1], "%x", &addr) != 1) {
        printf("Invalid I2C address: %s\n", argv[1]);
        return 1;
    }
    
    if (addr != 0x44 && addr != 0x45) {
        printf("Address must be 0x44 (13V input) or 0x45 (5.1V USB)\n");
        return 1;
    }

    int fd = wiringPiI2CSetup(addr);
    if (fd < 0) {
        printf("Failed to open I2C at 0x%02x\n", addr);
        return 1;
    }

    printf("INA219 @ 0x%02x initialized\n", addr);
    configure_ina219(fd);
    usleep(100000);  // 100ms settle

    float current_lsb = 3.2 / 32768.0f;  // 97.65625uA/LSB

    // Single measurement
    uint16_t raw_bus = read_bus_voltage(fd);
    float voltage = ((raw_bus >> 3) * 4.0f) / 1000.0f;   // mV → V

    int16_t raw_current = read_current(fd);
    float current = raw_current * current_lsb * 1000.0f;  // A → mA

    uint16_t raw_power = read_power(fd);
    float power = raw_power * current_lsb * 20.0f;        // Watts

    printf("Voltage: %.3f V Current: %.3f mA Power: %.3f W\n", 
           voltage, current, power);

    return 0;
}
