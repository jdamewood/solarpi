#include <stdio.h>
#include <wiringPiI2C.h>
#include <unistd.h>

#define INA219_ADDRESS 0x40 // Default address of the INA219 sensor
#define SHUNT_OHMS 0.1     // Value of the shunt resistor in Ohms
#define MAX_EXPECTED_AMPS 2.0 // Maximum expected current in Amps

int main() {
    int fd;
    float voltage, current, power;

    // Open I2C connection
    fd = wiringPiI2CSetup(INA219_ADDRESS);
    if (fd < 0) {
        printf("Failed to open I2C connection\n");
        return 1;
    }

    // Configure the INA219 sensor
    // This step would involve sending appropriate commands to the sensor over I2C
    // to set up the shunt resistor value, maximum expected current, and voltage range.
    // Refer to the INA219 datasheet for the exact commands and registers to write.

    while (1) {
        // Read voltage, current, and power from the sensor
        voltage = wiringPiI2CReadReg16(fd, 0x02); // Example register for voltage reading
        current = wiringPiI2CReadReg16(fd, 0x03); // Example register for current reading
        power = wiringPiI2CReadReg16(fd, 0x04);   // Example register for power reading

        // Convert raw values to meaningful units
        voltage /= 1000.0; // Assuming the voltage is returned in millivolts
        current /= 1000.0; // Assuming the current is returned in milliamps
        power /= 1000.0;   // Assuming the power is returned in milliwatts

        // Print the readings
        printf("Voltage: %.3f V\n", voltage);
        printf("Current: %.3f mA\n", current);
        printf("Power: %.3f mW\n", power);

        // Sleep for a second before the next read
        sleep(1);
    }

    return 0;
}
