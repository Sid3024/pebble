# Embedded Electronics Basics for Non-EEE Students

This note is a practical cheat sheet for students who are new to hardware. It focuses on the terms and interfaces you will see often when working with microcontrollers such as the ESP32.

## 1. The Big Picture

An embedded system usually has four basic parts:

- A **microcontroller** that runs the code.
- **Sensors** that measure something such as temperature, light, or motion.
- **Actuators** that do something such as turn on an LED, move a motor, or play sound.
- A **power source** such as USB, a battery, or an external supply.

The microcontroller reads inputs, makes decisions, and drives outputs.

## 2. Common Electrical Terms

### Voltage (V)

Voltage is the electrical "pressure" that pushes charge through a circuit.

- Common logic voltages in embedded systems: **3.3V** and **5V**.
- Many modern boards, including ESP32 boards, use **3.3V logic**.
- Applying **5V to a 3.3V-only pin can damage the board**.

### Current (A, mA)

Current is how much electrical charge is flowing.

- `A` means ampere.
- `mA` means milliampere, or one thousandth of an ampere.
- Example: `500 mA = 0.5 A`.

Devices draw the current they need. Your power supply must be able to provide enough current.

### Power (W)

Power is the rate of energy usage.

$$P = V \times I$$

Example: a `5V` device using `0.5A` consumes:

$$5 \times 0.5 = 2.5W$$

### Ground (GND)

Ground is the common reference point for the circuit.

- If two devices communicate, they usually need a **shared ground**.
- A missing common ground is a very common beginner wiring mistake.

## 3. Common Voltages You Will See

### 3.3V

- Very common for modern microcontrollers and sensors.
- Safe assumption for **ESP32**, **RP2040**, many IMUs, OLEDs, and digital sensors.

### 5V

- Common from USB power.
- Used by some modules, relays, servos, and older sensors.
- Not always safe as a logic level for 3.3V boards.

### 1.8V and Lower

- Found in some cameras, displays, memory chips, and advanced modules.
- Usually not beginner-friendly unless a breakout board handles level shifting.

## 4. Logic Levels

Digital pins normally read only two states:

- `LOW` means near `0V`
- `HIGH` means near the board's logic voltage, often `3.3V`

Important: a `HIGH` on one board is not always a safe `HIGH` on another board.

- A `5V HIGH` may be unsafe for a `3.3V` input.
- Use a **level shifter** when two devices use different logic voltages.

## 5. Input, Output, and GPIO

### GPIO

GPIO means **General Purpose Input/Output**.

These pins can often be configured in software as:

- Input: read a button or sensor state.
- Output: turn an LED on or off.
- Special function: act as I2C, SPI, UART, PWM, and more.

### Input Pins

Input pins read a voltage level.

- Example: a button press may pull a pin to ground.
- Floating inputs can behave unpredictably.
- Use **pull-up** or **pull-down** resistors so the pin has a known default state.

### Output Pins

Output pins drive a signal out.

- Good for LEDs, control lines, or communication signals.
- Do not assume a GPIO pin can safely power motors or large loads directly.

## 6. Pull-Up and Pull-Down Resistors

These resistors set a default logic state when nothing else is driving the pin.

- **Pull-up**: default state is `HIGH`.
- **Pull-down**: default state is `LOW`.

Example: many buttons are wired so pressing the button connects the pin to ground, while an internal pull-up keeps the pin `HIGH` when not pressed.

## 7. Analog vs Digital

### Digital Signals

Digital signals have two states, usually `LOW` and `HIGH`.

Examples:

- Button pressed or not pressed
- LED on or off
- Logic communication lines

### Analog Signals

Analog signals vary continuously.

Examples:

- Potentiometer position
- Microphone output
- Some analog sensors

Microcontrollers read analog voltages using an **ADC**.

- ADC means **Analog to Digital Converter**.
- The ADC converts a voltage into a number your code can use.

## 8. PWM in Simple Terms

PWM means **Pulse Width Modulation**.

It is a digital signal that switches on and off very quickly. By changing how long it stays on versus off, you can control average power.

Common uses:

- Dimming LEDs
- Controlling motor speed
- Creating simple tones with a buzzer

PWM is not true analog output, but it often behaves similarly for control tasks.

## 9. Common Communication Interfaces

### UART

UART is a simple serial communication interface.

- Common pins: `TX` and `RX`
- Often used for debug messages in the serial monitor
- Also used by GPS modules, some sensors, and other controllers

Good for beginners because it is easy to test and understand.

### I2C

I2C is a two-wire communication bus.

- Common pins: `SDA` and `SCL`
- Used by sensors, OLED displays, RTC modules, and many breakout boards

Why it is popular:

- Only two signal wires are needed
- Multiple devices can share the same bus

Important things to know:

- Each device needs a unique **address**
- I2C usually needs **pull-up resistors** on SDA and SCL
- The bus is slower than SPI, but wiring is simpler

Typical use cases:

- OLED display
- Real-time clock (RTC)
- Environmental sensors

### SPI

SPI is a faster communication interface than I2C for many use cases.

Common pins:

- `SCK` or `CLK`: clock
- `MOSI`: controller to peripheral data
- `MISO`: peripheral to controller data
- `CS` or `SS`: chip select

Why it is useful:

- Faster than I2C in many cases
- Good for displays, SD cards, and high-speed sensors

Tradeoff:

- Uses more wires than I2C
- Each device usually needs its own chip select line

### I2S

I2S is mainly used for digital audio.

Common uses:

- Microphones
- Audio DACs
- Speakers and amplifier modules

It is not the same as I2C even though the names look similar.

- **I2C** is for general device communication
- **I2S** is for streaming digital audio data

### One-Wire and Other Buses

You may also see other interfaces such as:

- **One-Wire** for some temperature sensors
- **CAN** in automotive and industrial systems
- **USB** for power and data

You do not need to master all of them at the start.

## 10. Typical Beginner Hardware Blocks

### Sensors

Sensors provide input data.

Examples:

- Temperature sensor
- Light sensor
- Motion sensor
- Accelerometer

### Actuators

Actuators create an output action.

Examples:

- LED
- Buzzer
- Relay
- Servo motor
- DC motor

### Displays

Displays give feedback to the user.

Examples:

- OLED screen
- LCD screen
- Seven-segment display

## 11. Power Rules That Save Boards

Before connecting anything, check these four things:

1. **Voltage**: Is the module powered by `3.3V` or `5V`?
2. **Logic level**: Are its signal pins `3.3V` safe?
3. **Current draw**: Can the board or supply provide enough current?
4. **Ground**: Do all communicating devices share a common ground?

Beginner rule: if you are not sure a module is `3.3V` safe, do not connect it directly to ESP32 GPIO pins.

## 12. What a Datasheet Usually Tells You

A datasheet is the official technical document for a chip or module. You do not need to read every page.

Start by looking for:

- Supply voltage range
- Logic voltage or input thresholds
- Pinout
- Communication interface
- Current consumption
- Absolute maximum ratings

The phrase **absolute maximum rating** means "do not exceed this, even briefly."

## 13. Common Beginner Mistakes

- Reversing `VCC` and `GND`
- Feeding `5V` logic into a `3.3V` pin
- Forgetting common ground
- Connecting motors directly to GPIO pins
- Ignoring current limits
- Using the wrong pin names for a bus
- Confusing **I2C** with **I2S**
- Assuming all modules work at the same voltage

## 14. Quick Mental Models

- **Voltage**: pressure
- **Current**: flow rate
- **Ground**: shared reference point
- **GPIO**: flexible pin controlled by software
- **I2C**: simple shared bus for many low-speed devices
- **SPI**: faster bus with more wires
- **I2S**: digital audio bus
- **UART**: simple serial text/data link
- **PWM**: fake analog using fast digital switching

## 15. Minimum Safe Workflow Before Wiring

1. Check the module's supply voltage.
2. Check the module's logic voltage.
3. Confirm the pin names from the module documentation.
4. Share ground between connected devices.
5. Start with a simple test example before combining many modules.

## 16. Practical Advice for This Project

For this project, you will often see modules such as:

- OLED displays
- RTC modules
- WiFi features built into the ESP32

Many classroom modules use **I2C**, so it is worth becoming comfortable with:

- `SDA`
- `SCL`
- device addresses
- pull-up resistors
- `3.3V` logic safety

When in doubt, slow down and verify the module voltage first. Most hardware mistakes happen before the code even starts running.
