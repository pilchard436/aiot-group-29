
# Reusable alarm clock from Lab 3 checkpoint 4.
# Importing this module performs all hardware setup (OLED, light sensor, piezo,
# NeoPixel, buttons, button IRQs) and schedules the alarm. One iteration of the
# main loop is exposed as step(); callers run their own `while True:` loop and
# can nudge `scroll_x` / `scroll_y` to shift the entire display.

from machine import RTC, I2C, Pin, ADC, PWM
import micropython
import neopixel
import time
import ssd1306

SCREEN_W = 128
SCREEN_H = 32

rtc = RTC()
rtc.datetime((2026, 10, 14, 1, 12, 0, 0, 0))

i2c = I2C(0, scl=Pin(20), sda=Pin(22), freq=400000)
oled = ssd1306.SSD1306_I2C(SCREEN_W, SCREEN_H, i2c)

light_sensor = ADC(Pin(36))
light_sensor.atten(ADC.ATTN_11DB)
light_sensor.width(ADC.WIDTH_12BIT)

MIN_CONTRAST = 1
MAX_CONTRAST = 255
CONTRAST_STEP = 8
LIGHT_SMOOTHING = 0.2

piezo = PWM(Pin(12))
piezo.freq(2000)
piezo.duty_u16(0)

neopixel_power = Pin(2, Pin.OUT)
neopixel_power.value(1)
np_led = neopixel.NeoPixel(Pin(0, Pin.OUT), 1)
np_led[0] = (0, 0, 0)
np_led.write()

ALARM_COLOR = (64, 0, 0)
RING_TOGGLE_MS = 250
RING_TIMEOUT_MS = 60000

button_a = Pin(15, Pin.IN, Pin.PULL_UP)
button_b = Pin(32, Pin.IN, Pin.PULL_UP)
button_c = Pin(14, Pin.IN, Pin.PULL_UP)

DEBOUNCE_MS = 50

(MODE_RUN, MODE_HOUR, MODE_MINUTE, MODE_SECOND,
 MODE_ALARM_HOUR, MODE_ALARM_MINUTE) = range(6)
NUM_MODES = 6
TIME_FIELDS = {
    MODE_HOUR: (4, 24),
    MODE_MINUTE: (5, 60),
    MODE_SECOND: (6, 60),
}
UNDERLINE_POS = {
    MODE_HOUR: (0, 9),
    MODE_MINUTE: (24, 9),
    MODE_SECOND: (48, 9),
    MODE_ALARM_HOUR: (48, 21),
    MODE_ALARM_MINUTE: (72, 21),
}

mode = MODE_RUN
needs_redraw = True

alarm_hours = 12
alarm_minutes = 1
alarm_enabled = True

ringing = False
ring_start_ms = 0
ring_toggle_ms = 0
ring_on = False
alarm_fired = False

# Display scroll offset. External code (e.g. the Lab 4 tilt-scrolling script)
# can mutate these to shift the entire rendered display.
scroll_x = 0
scroll_y = 0


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


def change_field(step):
    global alarm_hours, alarm_minutes, alarm_fired, needs_redraw

    if mode in TIME_FIELDS:
        index, limit = TIME_FIELDS[mode]
        now = list(rtc.datetime())
        now[index] = (now[index] + step) % limit
        now[7] = 0
        rtc.datetime(tuple(now))
    elif mode == MODE_ALARM_HOUR:
        alarm_hours = (alarm_hours + step) % 24
    elif mode == MODE_ALARM_MINUTE:
        alarm_minutes = (alarm_minutes + step) % 60
    else:
        return
    alarm_fired = False
    needs_redraw = True


def handle_a(_):
    global mode, needs_redraw
    if ringing:
        stop_ringing()
        return
    mode = (mode + 1) % NUM_MODES
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
        change_field(1)


def handle_c(_):
    if ringing:
        stop_ringing()
        return
    change_field(-1)


def _make_isr(handler):
    last_press_ms = 0

    def isr(_):
        nonlocal last_press_ms
        now = time.ticks_ms()
        if time.ticks_diff(now, last_press_ms) < DEBOUNCE_MS:
            return
        last_press_ms = now
        micropython.schedule(handler, 0)

    return isr


button_a.irq(trigger=Pin.IRQ_FALLING, handler=_make_isr(handle_a))
button_b.irq(trigger=Pin.IRQ_FALLING, handler=_make_isr(handle_b))
button_c.irq(trigger=Pin.IRQ_FALLING, handler=_make_isr(handle_c))


def light_to_contrast(light):
    return MIN_CONTRAST + (MAX_CONTRAST - MIN_CONTRAST) * light // 4095


def put_text(s, x, y):
    # Draw text with the module's scroll offset, replicating it so content
    # that leaves one edge reappears on the opposite edge.
    px = (x + scroll_x) % SCREEN_W
    py = (y + scroll_y) % SCREEN_H
    oled.text(s, px, py)
    oled.text(s, px - SCREEN_W, py)
    oled.text(s, px, py - SCREEN_H)
    oled.text(s, px - SCREEN_W, py - SCREEN_H)


def put_hline(x, y, w):
    px = (x + scroll_x) % SCREEN_W
    py = (y + scroll_y) % SCREEN_H
    oled.framebuf.hline(px, py, w, 1)
    oled.framebuf.hline(px - SCREEN_W, py, w, 1)
    oled.framebuf.hline(px, py - SCREEN_H, w, 1)
    oled.framebuf.hline(px - SCREEN_W, py - SCREEN_H, w, 1)


def draw(hours, minutes, seconds, light, contrast):
    oled.fill(0)
    put_text("{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds), 0, 0)
    put_text("Alarm {:02d}:{:02d} {}".format(
        alarm_hours, alarm_minutes, "ON" if alarm_enabled else "OFF"), 0, 12)
    if ringing:
        put_text("ALARM!", 0, 24)
    else:
        put_text("L:{:4d} C:{:3d}".format(light, contrast), 0, 24)
    if mode != MODE_RUN:
        x, y = UNDERLINE_POS[mode]
        put_hline(x, y, 16)
        put_text("SET", 104, 0)
    oled.show()


# Loop state kept across step() calls.
_last_second = -1
_light = light_sensor.read()
_contrast = light_to_contrast(_light)
oled.contrast(_contrast)


def step():
    global _last_second, _light, _contrast
    global alarm_fired, needs_redraw
    global ring_toggle_ms

    smoothed = (1 - LIGHT_SMOOTHING) * _light + LIGHT_SMOOTHING * light_sensor.read()
    _light = round(smoothed)

    target = light_to_contrast(_light)
    if (abs(target - _contrast) >= CONTRAST_STEP
            or (target != _contrast and target in (MIN_CONTRAST, MAX_CONTRAST))):
        _contrast = target
        oled.contrast(_contrast)

    year, month, day, weekday, hours, minutes, seconds, _ = rtc.datetime()

    at_alarm_time = hours == alarm_hours and minutes == alarm_minutes
    if not at_alarm_time:
        alarm_fired = False
    elif alarm_enabled and not alarm_fired and not ringing and mode == MODE_RUN:
        alarm_fired = True
        start_ringing()

    if ringing:
        now = time.ticks_ms()
        if time.ticks_diff(now, ring_start_ms) >= RING_TIMEOUT_MS:
            stop_ringing()
        elif time.ticks_diff(now, ring_toggle_ms) >= RING_TOGGLE_MS:
            ring_toggle_ms = now
            set_ring_output(not ring_on)

    if seconds != _last_second or needs_redraw:
        _last_second = seconds
        needs_redraw = False
        draw(hours, minutes, seconds, _light, _contrast)


def request_redraw():
    global needs_redraw
    needs_redraw = True


def run():
    while True:
        step()
        time.sleep_ms(20)


if __name__ == "__main__":
    print("alarm_clock stand-alone")
    run()
