#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <avr/wdt.h>

// Create an instance of the ADS1115 ADC
Adafruit_ADS1115 ads;

// Create an instance of the OLED display
#define SCREEN_WIDTH 128  // OLED display width, in pixels
#define SCREEN_HEIGHT 64   // OLED display height, in pixels
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

double previousMicros = 0;  // Stores last time the sample was taken
const float sampleRate = 100.0; // Sampling rate in Hz
const float intervalMicros = 1000000.0 / sampleRate; // Sampling interval in microseconds

unsigned long previousDisplayUpdate = 0; // Last time the display was updated
const unsigned long displayUpdateInterval = 100; // Update display every 500 ms
bool newMax = false; // Flag to indicate a new max has been registered

float currentVoltage = 0.0;
float maxVoltage = 0.0;
unsigned long maxVoltageTimestamp = 0; // Timestamp for max voltage

// Alert variables
bool alertShown = false; // To track if alert has been shown
unsigned long alertStart = 0; // Start time for alert
const float voltageThreshold = 100.0; // Voltage threshold for alert (in mV)
const unsigned long alertDuration = 5 * 1000; // 4 hours in milliseconds

double startDebugMilis = 0;
double debugMilis = 0;

// Dynamic Gain Control variables
adsGain_t gain[6] = {GAIN_TWOTHIRDS, GAIN_ONE, GAIN_TWO, GAIN_FOUR, GAIN_EIGHT, GAIN_SIXTEEN};  // Array of gain settings
const char* gainNames[6] = {
  "GAIN_TWOTHIRDS",
  "GAIN_ONE",
  "GAIN_TWO",
  "GAIN_FOUR",
  "GAIN_EIGHT",
  "GAIN_SIXTEEN"
};

const char* gainNumbers[6] = {"G-2/3", "G-1", "G-2", "G-4", "G-8", "G-16"};
int g = 2; // Start with GAIN_FOUR (±1.024V)
float adc, volt;

// unsigned long previousResetMicros = 0;  // To track the last reset time 
// const unsigned long resetInterval = 3600 * 1000000; // reset time in Microseconds
// bool resetTriggered = false;  // To avoid re-triggering resets

// Timing variables for LED on pin 12
unsigned long previousLEDTime = 0;  // Last time the LED was toggled
const unsigned long ledOnDuration = 500;  // Time to keep the LED on (1 second)
const unsigned long ledOffDuration = 500;  // Time to wait before turning on again (3 seconds)
bool ledState = LOW;  // Track the current LED state (HIGH = on, LOW = off)
int brightness = 0;  // how bright the LED is
int fadeAmount = 2;  // how many points to fade the LED by

// ------------------------------
// ------------------------------


void setup(void) {

  Serial.begin(230400);  // Initialize Serial communication
  if (!ads.begin(0x48)) {  // Initialize the ADS1115
    Serial.println("Failed to initialize ADS.");
    while (1);
  }

  ads.setGain(gain[g]);  // Set initial gain

  // Enable the WDT with a 2-second timeout
  wdt_enable(WDTO_2S);

  // Initialize the OLED display
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("SSD1306 allocation failed");
    for (;;);
  } else {
    Serial.println("SSD1306 allocation successful");
  }
  // Set brightness (contrast level)
  display.ssd1306_command(SSD1306_SETCONTRAST);  // Command to set contrast
  display.ssd1306_command(0x00);  // Adjust value here (0x00 = min brightness, 0xFF = max)
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.display();
  
    digitalWrite(12, HIGH);  // Turn on the LED
    delay(1000);                    // Wait for 1 second
    digitalWrite(12, LOW);   // Turn off the LED
    // delay(250);                    // Wait for 1 second
  
}

void loop(void) {
  wdt_reset();

  unsigned long currentMicros = micros();
  unsigned long currentMillis = millis();

  // Check if it's time to reset the board
  // if (currentMicros - previousResetMicros >= resetInterval) {
  //   previousResetMicros = currentMicros; // Update the last reset time
  //   reset();  // Call the reset function to restart the board
  // }

  // fade();
    // LED control logic: turn on for 1 second, every 3 seconds
  if (ledState == LOW && currentMillis - previousLEDTime >= ledOffDuration) {
    // Turn the LED on
    digitalWrite(12, HIGH);
    ledState = HIGH;
    previousLEDTime = currentMillis;  // Reset the timer for LED on duration
  } 
  else if (ledState == HIGH && currentMillis - previousLEDTime >= ledOnDuration) {
    // Turn the LED off
    digitalWrite(12, LOW);
    ledState = LOW;
    previousLEDTime = currentMillis;  // Reset the timer for the LED off duration
  }

  // Check if it's time to sample
  if (currentMicros - previousMicros >= intervalMicros) {
    previousMicros = currentMicros;  // Update time

    startDebugMilis = millis();
    dynamicGainAdjustment();  // Adjust gain dynamically

    // adc = ads.readADC_SingleEnded(0);  // Get average ADC value from channel 0
    adc = samples(0);  // Get average ADC value from channel 0
    currentVoltage = voltage(adc, g);  // Convert ADC to voltage

    // Update max voltage and timestamp if current voltage is greater
    if (abs(currentVoltage) > maxVoltage) {
      maxVoltage = abs(currentVoltage);
      maxVoltageTimestamp = millis();  // Store the time of max voltage
      newMax = true;
    }

    if (newMax){
      // updateDisplay();
      // digitalWrite(12, HIGH);  // Turn on the LED
      // delay(1000);                    // Wait for 1 second
      // digitalWrite(12, LOW);   // Turn off the LED
      newMax = false;
    }

    // Check if max voltage exceeds the threshold
    if (maxVoltage >= voltageThreshold && !alertShown) {
      alertShown = true; // Set alert flag
      alertStart = millis(); // Record the start time of the alert
    }

    // Send data to Serial for debugging
    debugMilis = millis();
    Serial.println(adc);
    // Serial.println(debugMilis - startDebugMilis);
    // Serial.print("ADC: "); Serial.println(adc);
    // Serial.print("Voltage: "); Serial.println(currentVoltage);
  }

  // Update the display every 500 ms
  if (millis() - previousDisplayUpdate >= displayUpdateInterval) {
    previousDisplayUpdate = millis();
    updateDisplay();
  }

  wdt_reset();
}

// Dynamic gain adjustment function
void dynamicGainAdjustment() {
  // adc = samples(0);  // Get average ADC value
  adc = ads.readADC_SingleEnded(0);

  while (1) {
    if (adc >= 30000 && g > 0) {  // If ADC is getting pegged at maximum and not the widest range, reduce gain
      // Serial.println("Reducing gain..");
      g--;
      ads.setGain(gain[g]);
      Serial.println(gainNames[g]);
    } else if (adc <= 7000 && g < 5) {  // If ADC is too low and not the narrowest range, increase gain
      // Serial.println("Increasing gain..");
      g++;
      ads.setGain(gain[g]);
      Serial.println(gainNames[g]);
    } else {
      break;
    }
    // adc = samples(0);  // Recalculate ADC after adjusting gain
    adc = ads.readADC_SingleEnded(0);
  }
}

// Perform multiple iterations to get higher accuracy ADC values (reduce noise)
float samples(int pin) {
  float n = 3.0;  // Number of iterations to perform
  float sum = 0.0;  // Store sum as a 32-bit number
  for (int i = 0; i < n; i++) {
    float value = ads.readADC_SingleEnded(pin);
    sum = sum + value;
    // delay(1);  // Small delay between samples
  }
  float average = sum / n;   // Get average value
  return average;
}

// Get voltage based on gain setting
float voltage(float adc, int gain) {
  float V;
  switch (gain) {
    case 0:  // 2/3x gain setting for ±6.144 V
      V = adc * 0.1875;
      break;
    case 1:  // 1x gain setting for ±4.096 V
      V = adc * 0.125;
      break;
    case 2:  // 2x gain setting for ±2.048 V
      V = adc * 0.0625;
      break;
    case 3:  // 4x gain setting for ±1.024 V
      V = adc * 0.03125;
      break;
    case 4:  // 8x gain setting for ±0.512 V
      V = adc * 0.015625;
      break;
    case 5:  // 16x gain setting for ±0.256 V
      V = adc * 0.0078125;
      break;
    default:
      V = 0.0;
  }
  return V;
}

// the loop routine runs over and over again forever:
void fade() {
  // set the brightness of pin 9:
  analogWrite(9, brightness);

  // change the brightness for next time through the loop:
  brightness = brightness + fadeAmount * 0.5;

  // reverse the direction of the fading at the ends of the fade:
  if (brightness <= 0 || brightness >= 25) {
    fadeAmount = -fadeAmount;
  }
  // wait for 30 milliseconds to see the dimming effect
  // delay(30);
}

void updateDisplay() {
  display.clearDisplay();

  // Display current voltage
  display.setCursor(0, 0);
  display.setTextSize(2);
  display.print(currentVoltage, 3); // Print current voltage in mV
  display.setTextSize(1);
  display.println(" mV");

  // Display maximum voltage and timestamp
  display.setCursor(0, 25);
  display.setTextSize(1);
  display.print("Max: ");
  display.setTextSize(2);
  display.print(maxVoltage, 1);  // Print max voltage in mV
  display.setTextSize(1);
  display.println(" mV");
  display.setCursor(0, 50);
  display.print("at ");

  // Format timestamp as HH:MM:SS
  display.setTextSize(1);
  unsigned long elapsedMillis = maxVoltageTimestamp;
  unsigned long hours = (elapsedMillis / 3600000) % 24;
  unsigned long minutes = (elapsedMillis / 60000) % 60;
  unsigned long seconds = (elapsedMillis / 1000) % 60;
  display.print(hours < 10 ? "0" : ""); // Add leading zero
  display.print(hours);
  display.print("h");
  display.print(minutes < 10 ? "0" : ""); // Add leading zero
  display.print(minutes);
  display.print("m");
  display.print(seconds < 10 ? "0" : ""); // Add leading zero
  display.print(seconds);
  display.print("s");

  // Display current gain setting
  display.setCursor(100, 50);
  display.print(gainNumbers[g]);

  // Show "(!)" at the top right if alert is active
  if (alertShown && (millis() - alertStart) <= alertDuration) {
    display.setCursor(SCREEN_WIDTH - 16, 0);
    display.setTextSize(2);
    display.println("!");
  }

  display.display();  // Push updates to the display
}

void reset() {
  if (!resetTriggered) {  // Only execute if not already triggered
    resetTriggered = true;  // Mark that reset has been triggered

    // Blink the LED 3 times, 1 second each
    for (int i = 0; i < 5; i++) {
      digitalWrite(13, HIGH);  // Turn on the LED
      delay(200);                    // Wait for 1 second
      digitalWrite(13, LOW);   // Turn off the LED
      delay(200);                    // Wait for 1 second
    }
    wdt_enable(WDTO_1S);  // Enable watchdog timer to reset after 2 seconds
    while (true) {}       // Wait for watchdog to trigger reset
  }
}
