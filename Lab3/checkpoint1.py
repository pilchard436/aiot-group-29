from machine import RTC, I2C, Pin
import micropython
import time
import ssd1306

# The RTC keeps counting while the board is powered, but we reset it to a
# fixed value on every boot so the starting time is predictable.
# Tuple format: (year, month, day, weekday, hours, minutes, seconds, subseconds)
# weekday: 0 = Monday ... 6 = Sunday
rtc = RTC()
rtc.datetime((2026, 9, 30, 2, 12, 0, 0, 0))

# The OLED FeatherWing is a 128x32 SSD1306 on the Feather's I2C pins.
# Feather ESP32 V2: SCL = GPIO 20, SDA = GPIO 22.
i2c = I2C(0, scl=Pin(20), sda=Pin(22), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 32, i2c)

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# OLED FeatherWing buttons. Each connects its pin to GND when pressed, so the
# internal pull-up keeps the pin HIGH when released and a press is a falling edge.
#   A: cycle mode (run -> set hour -> set minute -> set second -> run)
#   B: increment the selected field
#   C: decrement the selected field
button_a = Pin(15, Pin.IN, Pin.PULL_UP)
button_b = Pin(32, Pin.IN, Pin.PULL_UP)
button_c = Pin(14, Pin.IN, Pin.PULL_UP)

DEBOUNCE_MS = 50

# Mode 0 is normal running; modes 1-3 select which field the buttons edit.
MODE_RUN, MODE_HOUR, MODE_MINUTE, MODE_SECOND = 0, 1, 2, 3
# Index into the rtc.datetime() tuple and wrap-around limit for each field.
FIELDS = {
    MODE_HOUR: (4, 24),
    MODE_MINUTE: (5, 60),
    MODE_SECOND: (6, 60),
}

mode = MODE_RUN
needs_redraw = True


def change_field(step):
    global needs_redraw

    if mode == MODE_RUN:
        return
    index, limit = FIELDS[mode]
    now = list(rtc.datetime())
    now[index] = (now[index] + step) % limit
    now[7] = 0  # restart the subsecond counter so the new second is a full one
    rtc.datetime(tuple(now))
    needs_redraw = True


def handle_a(_):
    global mode, needs_redraw
    mode = (mode + 1) % 4
    needs_redraw = True


def handle_b(_):
    change_field(1)


def handle_c(_):
    change_field(-1)


def make_isr(handler):
    # Each button gets its own debounce timestamp so presses on different
    # buttons do not block each other.
    last_press_ms = 0

    def isr(_):
        nonlocal last_press_ms

        now = time.ticks_ms()
        # Mechanical buttons can rapidly switch between HIGH and LOW while being
        # pressed. Ignore those false edges for 50 ms after a valid press.
        if time.ticks_diff(now, last_press_ms) < DEBOUNCE_MS:
            return

        last_press_ms = now
        # Changing the RTC and redrawing are too slow for an ISR, so queue the
        # work for normal execution and keep the interrupt handler short.
        micropython.schedule(handler, 0)

    return isr


button_a.irq(trigger=Pin.IRQ_FALLING, handler=make_isr(handle_a))
button_b.irq(trigger=Pin.IRQ_FALLING, handler=make_isr(handle_b))
button_c.irq(trigger=Pin.IRQ_FALLING, handler=make_isr(handle_c))


def draw(year, month, day, weekday, hours, minutes, seconds):
    oled.fill(0)
    oled.text("{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds), 0, 0)
    oled.text("{} {:04d}-{:02d}-{:02d}".format(
        DAYS[weekday], year, month, day), 0, 12)

    if mode != MODE_RUN:
        # Underline the field being edited. Each character is 8 px wide and
        # the fields start at columns 0, 3, and 6 of "HH:MM:SS".
        x = (mode - 1) * 24
        # The provided driver has no hline(), so draw on its framebuffer.
        oled.framebuf.hline(x, 9, 16, 1)
        oled.text("SET", 104, 0)

    oled.show()


print("Checkpoint 1 - Part 2 Task 3")

last_second = -1

while True:
    year, month, day, weekday, hours, minutes, seconds, _ = rtc.datetime()

    # Redraw when the second changes or a button changed something, to avoid
    # needless I2C traffic.
    if seconds != last_second or needs_redraw:
        last_second = seconds
        needs_redraw = False
        draw(year, month, day, weekday, hours, minutes, seconds)

    time.sleep_ms(20)
