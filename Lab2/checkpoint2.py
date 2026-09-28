import machine
import time

# Initialize GPIO 12 as an input pin with the internal pull-up resistor enabled
# mpfshell -nc "open tty.usbserial-5B8E6152811; repl"

button = machine.Pin(27, machine.Pin.IN, machine.Pin.PULL_UP)

print("Reading button state... Press Ctrl+C to stop.")

last = 1

while True:
    current = button.value()
    if last == 1 and current == 0:
        print("Button Pressed!")
    last = current
    time.sleep(0.05)
