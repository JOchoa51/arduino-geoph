# ADS1115 Voltage Measurement and OLED Display Project

This project is an Arduino-based setup designed to measure voltage using the ADS1115 analog-to-digital converter and display the results on an OLED screen. The system can be used for real-time monitoring of analog signals and visualizing voltage readings.

## Features

- **Voltage Measurement**: Reads analog signals with high precision using the ADS1115 ADC module, performing gain adjustment on the fly.
- **OLED Display Integration**: Displays voltage readings in real-time on an OLED screen.
- **Arduino Compatibility**: Works with Arduino Uno or compatible boards.

## Requirements

### Hardware
- Arduino Uno (or compatible)
- ADS1115 Analog-to-Digital Converter
- OLED Display (I2C interface)
- Jumper wires
- Breadboard or PCB

### Software
- Arduino IDE
- Required Libraries:
  - `Adafruit_ADS1X15`
  - `Adafruit_GFX`
  - `Adafruit_SSD1306`
  - `Wire`

## Installation

1. Connect the ADS1115 and OLED display to the Arduino as per their datasheets. Ensure the I2C addresses are set correctly.
2. Download and install the required libraries in the Arduino IDE:
   ```bash
   Arduino IDE -> Tools -> Manage Libraries -> Search and Install
   ```
   - `Adafruit_ADS1X15`
   - `Adafruit_GFX`
   - `Adafruit_SSD1306`

3. Load the appropriate `.ino` file to the Arduino:
   - **ADS1115_OLEDdraw.ino**: Includes functionality for visualizing voltage with graphics.
   - **measureVoltageADS1115.ino**: Focused on precise voltage measurement without visualization.

4. Compile and upload the code to the Arduino via the Arduino IDE.

## Usage

1. Power on the Arduino and connected components.
2. Observe the OLED screen for real-time voltage readings.
3. If using **ADS1115_OLEDdraw.ino**, graphical representations of the readings will also be displayed.


## Wiring Diagram

### ADS1115 Connections:
- VCC → Arduino 5V
- GND → Arduino GND
- SCL → Arduino A5 (SCL)
- SDA → Arduino A4 (SDA)

### OLED Connections:
- VCC → Arduino 3.3V or 5V
- GND → Arduino GND
- SCL → Arduino A5 (SCL)
- SDA → Arduino A4 (SDA)

## Example Output

### Serial Monitor (Voltage Measurement):
- `Voltage: 1.23 V`
- `Voltage: 3.45 V`

### OLED Display:
Displays the current voltage in real-time with a clear and concise layout.

## Notes

- Ensure the I2C connections and addresses for the ADS1115 and OLED are correct.
- Modify the code if needed to accommodate custom display sizes or specific voltage ranges.
- Optionally, you can add a voltage amplifier to detect very weak signals.

## Contact

For questions or support, please contact:  
Jesús Ochoa Contreras  
[ochoacontrerasjesus8@gmail.com](mailto:ochoacontrerasjesus8@gmail.com)
