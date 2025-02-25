from machine import Pin
from onewire import OneWire
from ds18x20 import DS18X20
import time

class DS18B20:
    def __init__(self, power_pin, data_pin):
        """Initialize the DS18B20 temperature sensor.

        Args:
            power_pin (int): GPIO pin number for VCC
            data_pin (int): GPIO pin number for sensor data
        """
        # Setup power pin
        self.power = Pin(power_pin, Pin.OUT)
        self.power.value(1)  # Turn on power to sensor

        # Allow time for sensor to power up
        time.sleep_ms(100)

        # Create the onewire object
        self.dat = Pin(data_pin)
        self.ds = DS18X20(OneWire(self.dat))

        # Scan for devices
        self.roms = self.ds.scan()
        if not self.roms:
            raise RuntimeError("No DS18B20 devices found")

    def read_temps(self):
        """Read temperature from the sensor.

        Returns:
            tuple: Temperature in (Celsius, Fahrenheit)
        """
        self.ds.convert_temp()
        # Wait for conversion to complete (750ms is required)
        time.sleep_ms(750)

        # Read temperature from first sensor
        temp_c = self.ds.read_temp(self.roms[0])
        temp_f = (temp_c * 9/5) + 32

        return temp_f

# Example usage
def main():
    try:
        # Initialize sensor with GPIO14 for power and GPIO15 for data
        sensor = DS18B20(power_pin=14, data_pin=15)

        while True:
            try:
                temp_f = sensor.read_temps()
                print(f"Temperature: {temp_f:.2f}°F")
                time.sleep(2)
            except Exception as e:
                print(f"Error reading temperature: {e}")
                time.sleep(2)

    except KeyboardInterrupt:
        print("\nProgram stopped by user")
    except Exception as e:
        print(f"Error initializing sensor: {e}")

if __name__ == "__main__":
    main()
