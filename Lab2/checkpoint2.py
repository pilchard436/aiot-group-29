import machine
import time
from button_debounce import read_button, setup_button

# The button is connected between GPIO 27 and GND. The pull-up keeps the pin
# HIGH when released, so pressing the button changes the input from HIGH to LOW.
# mpfshell -nc "open tty.usbserial-5B8E6152811; repl"

button = machine.Pin(27, machine.Pin.IN, machine.Pin.PULL_UP)

print("Reading button state... Press Ctrl+C to stop.")

last_button_state = setup_button(button, debounce_ms=50)

while True:
    button_state = read_button()
    if button_state == 0 and last_button_state == 1:
        print("Button Pressed!")
    last_button_state = button_state
    time.sleep_ms(1)
