import machine
import micropython
import time

# The button is connected between GPIO 27 and GND. The pull-up keeps the pin
# HIGH when released, so pressing the button changes the input from HIGH to LOW.
# mpfshell -nc "open tty.usbserial-5B8E6152811; repl"

button = machine.Pin(27, machine.Pin.IN, machine.Pin.PULL_UP)

print("Reading button state... Press Ctrl+C to stop.")

last_press_ms = 0


def report_button_press(_):
    # Printing is deferred until after the ISR because I/O is too slow for an ISR.
    print("Button Pressed!")


def button_isr(_):
    global last_press_ms

    now = time.ticks_ms()
    # Mechanical buttons can rapidly switch between HIGH and LOW while being
    # pressed. Ignore those false edges for 50 ms after a valid press.
    if time.ticks_diff(now, last_press_ms) < 50:
        return

    last_press_ms = now
    # Queue the print for normal execution; keep the interrupt handler short.
    micropython.schedule(report_button_press, 0)


# A press is a falling edge because the pull-up changes the pin from HIGH to LOW.
button.irq(trigger=machine.Pin.IRQ_FALLING, handler=button_isr)

while True:
    # The button is handled by the interrupt, so the main loop does not poll it.
    time.sleep(1)
