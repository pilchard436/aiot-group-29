from machine import RTC, I2C, Pin, PWM
import micropython
import neopixel
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

# Audio cue: piezo speaker driven by PWM on GPIO 12, silent until the alarm.
piezo = PWM(Pin(12))
piezo.freq(2000)
piezo.duty_u16(0)

# Visual cue: the Feather's onboard NeoPixel on GPIO 0. GPIO 2 switches on
# its power.
neopixel_power = Pin(2, Pin.OUT)
neopixel_power.value(1)
np_led = neopixel.NeoPixel(Pin(0, Pin.OUT), 1)
np_led[0] = (0, 0, 0)
np_led.write()

ALARM_COLOR = (64, 0, 0)
# The piezo and NeoPixel toggle together at this interval while ringing.
RING_TOGGLE_MS = 250
# Stop ringing automatically if nobody dismisses the alarm.
RING_TIMEOUT_MS = 60000

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# OLED FeatherWing buttons. Each connects its pin to GND when pressed, so the
# internal pull-up keeps the pin HIGH when released and a press is a falling edge.
#   A: cycle mode (run -> set alarm hour -> set alarm minute -> run)
#   B: increment the selected field; in run mode, turn the alarm on/off
#   C: decrement the selected field
# While the alarm is ringing, any button dismisses it.
button_a = Pin(15, Pin.IN, Pin.PULL_UP)
button_b = Pin(32, Pin.IN, Pin.PULL_UP)
button_c = Pin(14, Pin.IN, Pin.PULL_UP)

DEBOUNCE_MS = 50

MODE_RUN, MODE_ALARM_HOUR, MODE_ALARM_MINUTE = 0, 1, 2

mode = MODE_RUN
needs_redraw = True

# Default alarm one minute after boot so it is quick to demo.
alarm_hours = 12
alarm_minutes = 1
alarm_enabled = True

ringing = False
ring_start_ms = 0
ring_toggle_ms = 0
ring_on = False
# Set once the alarm fires so it does not retrigger during the same minute.
alarm_fired = False


def set_ring_output(on):
    global ring_on
    ring_on = on
    piezo.duty_u16(32768 if on else 0)
    np_led[0] = ALARM_COLOR if on else (0, 0, 0)
    np_led.write()


def start_ringing():
    global ringing, ring_start_ms, ring_toggle_ms, needs_redraw
    ringing = True
    ring_start_ms = ring_toggle_ms = time.ticks_ms()
    set_ring_output(True)
    needs_redraw = True
    print("Alarm ringing")


def stop_ringing():
    global ringing, needs_redraw
    ringing = False
    set_ring_output(False)
    needs_redraw = True
    print("Alarm stopped")


def change_alarm(step):
    global alarm_hours, alarm_minutes, alarm_fired, needs_redraw
    if mode == MODE_ALARM_HOUR:
        alarm_hours = (alarm_hours + step) % 24
    elif mode == MODE_ALARM_MINUTE:
        alarm_minutes = (alarm_minutes + step) % 60
    # A new alarm time should be able to fire, even within the current minute.
    alarm_fired = False
    needs_redraw = True


def handle_a(_):
    global mode, needs_redraw
    if ringing:
        stop_ringing()
        return
    mode = (mode + 1) % 3
    needs_redraw = True


def handle_b(_):
    global alarm_enabled, needs_redraw
    if ringing:
        stop_ringing()
        return
    if mode == MODE_RUN:
        alarm_enabled = not alarm_enabled
        needs_redraw = True
    else:
        change_alarm(1)


def handle_c(_):
    if ringing:
        stop_ringing()
        return
    if mode != MODE_RUN:
        change_alarm(-1)


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
        # Updating state and redrawing are too slow for an ISR, so queue the
        # work for normal execution and keep the interrupt handler short.
        micropython.schedule(handler, 0)

    return isr


button_a.irq(trigger=Pin.IRQ_FALLING, handler=make_isr(handle_a))
button_b.irq(trigger=Pin.IRQ_FALLING, handler=make_isr(handle_b))
button_c.irq(trigger=Pin.IRQ_FALLING, handler=make_isr(handle_c))


def draw(year, month, day, weekday, hours, minutes, seconds):
    oled.fill(0)
    oled.text("{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds), 0, 0)
    oled.text("Alarm {:02d}:{:02d} {}".format(
        alarm_hours, alarm_minutes, "ON" if alarm_enabled else "OFF"), 0, 12)

    if ringing:
        oled.text("ALARM!", 0, 24)
    else:
        oled.text("{} {:04d}-{:02d}-{:02d}".format(
            DAYS[weekday], year, month, day), 0, 24)

    if mode != MODE_RUN:
        # Underline the alarm field being edited. Each character is 8 px wide
        # and the fields start at columns 6 and 9 of "Alarm HH:MM".
        x = 48 if mode == MODE_ALARM_HOUR else 72
        # The provided driver has no hline(), so draw on its framebuffer.
        oled.framebuf.hline(x, 21, 16, 1)
        oled.text("SET", 104, 0)

    oled.show()


print("Checkpoint 3 - Part 3 Task 1")

last_second = -1

while True:
    year, month, day, weekday, hours, minutes, seconds, _ = rtc.datetime()

    at_alarm_time = hours == alarm_hours and minutes == alarm_minutes
    if not at_alarm_time:
        # Re-arm once the alarm minute has passed.
        alarm_fired = False
    elif alarm_enabled and not alarm_fired and not ringing:
        alarm_fired = True
        start_ringing()

    if ringing:
        now = time.ticks_ms()
        if time.ticks_diff(now, ring_start_ms) >= RING_TIMEOUT_MS:
            stop_ringing()
        elif time.ticks_diff(now, ring_toggle_ms) >= RING_TOGGLE_MS:
            # Beep and flash in sync, without blocking the clock or buttons.
            ring_toggle_ms = now
            set_ring_output(not ring_on)

    # Redraw when the second changes or something else changed, to avoid
    # needless I2C traffic.
    if seconds != last_second or needs_redraw:
        last_second = seconds
        needs_redraw = False
        draw(year, month, day, weekday, hours, minutes, seconds)

    time.sleep_ms(20)
