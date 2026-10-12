# Lab 4 - Checkpoint 1
# Lab 3 checkpoint 4 (alarm clock with light-adaptive OLED) + ADXL345 tilt
# scrolling. Tilt the board far enough along one of the four principal
# directions and the OLED content scrolls that way, wrapping at the edges.
#
# ADXL345 registers used:
#   0x00 DEVID       expect 0xE5
#   0x2C BW_RATE     0x0A -> 100 Hz output data rate
#   0x2D POWER_CTL   0x08 -> measure mode on
#   0x2E INT_ENABLE  0x00 -> no interrupts
#   0x31 DATA_FORMAT 0x00 -> +/-2g, right-justified, 10-bit
#   0x38 FIFO_CTL    0x00 -> bypass FIFO
#   0x32..0x37       X0,X1,Y0,Y1,Z0,Z1 data registers

from machine import RTC, I2C, SPI, Pin, ADC, PWM
import micropython
import neopixel
import time
import ssd1306

# === RTC ===
rtc = RTC()
rtc.datetime((2026, 10, 12, 0, 12, 0, 0, 0))

# === OLED ===
i2c = I2C(0, scl=Pin(20), sda=Pin(22), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 32, i2c)
SCREEN_W = 128
SCREEN_H = 32

# === Light sensor + contrast control ===
light_sensor = ADC(Pin(36))
light_sensor.atten(ADC.ATTN_11DB)
light_sensor.width(ADC.WIDTH_12BIT)

MIN_CONTRAST = 1
MAX_CONTRAST = 255
CONTRAST_STEP = 8
LIGHT_SMOOTHING = 0.2

# === Alarm outputs ===
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

# === Buttons ===
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


# === ADXL345 over SPI ===
spi = SPI(1, baudrate=5000000, polarity=1, phase=1,
          sck=Pin(5), mosi=Pin(19), miso=Pin(21))
cs = Pin(33, Pin.OUT, value=1)

SPI_READ = 0x80
SPI_MULTI = 0x40

REG_DEVID = 0x00
REG_BW_RATE = 0x2C
REG_POWER_CTL = 0x2D
REG_INT_ENABLE = 0x2E
REG_DATA_FORMAT = 0x31
REG_DATAX0 = 0x32
REG_FIFO_CTL = 0x38


def write_reg(addr, val):
    cs.value(0)
    spi.write(bytes([addr & 0x3F, val]))
    cs.value(1)


def read_reg(addr):
    cs.value(0)
    spi.write(bytes([addr | SPI_READ]))
    buf = bytearray(1)
    spi.readinto(buf)
    cs.value(1)
    return buf[0]


def read_xyz():
    cs.value(0)
    spi.write(bytes([REG_DATAX0 | SPI_READ | SPI_MULTI]))
    buf = bytearray(6)
    spi.readinto(buf)
    cs.value(1)
    x = buf[0] | (buf[1] << 8)
    y = buf[2] | (buf[3] << 8)
    z = buf[4] | (buf[5] << 8)
    if x & 0x8000:
        x -= 0x10000
    if y & 0x8000:
        y -= 0x10000
    if z & 0x8000:
        z -= 0x10000
    return x, y, z


device_id = read_reg(REG_DEVID)
print("ADXL345 DEVID: 0x{:02X}".format(device_id))
if device_id != 0xE5:
    print("WARNING: ADXL345 not detected (expected 0xE5)")

write_reg(REG_DATA_FORMAT, 0x00)
write_reg(REG_BW_RATE, 0x0A)
write_reg(REG_INT_ENABLE, 0x00)
write_reg(REG_FIFO_CTL, 0x00)
write_reg(REG_POWER_CTL, 0x08)
time.sleep_ms(10)

# Scroll offset applied to every text position when drawing.
scroll_x = 0
scroll_y = 0
TILT_THRESHOLD = 80  # ~0.3 g at 256 LSB/g
SCROLL_STEP = -2

# === Alarm helpers ===
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


def make_isr(handler):
    last_press_ms = 0

    def isr(_):
        nonlocal last_press_ms

        now = time.ticks_ms()
        if time.ticks_diff(now, last_press_ms) < DEBOUNCE_MS:
            return

        last_press_ms = now
        micropython.schedule(handler, 0)

    return isr


button_a.irq(trigger=Pin.IRQ_FALLING, handler=make_isr(handle_a))
button_b.irq(trigger=Pin.IRQ_FALLING, handler=make_isr(handle_b))
button_c.irq(trigger=Pin.IRQ_FALLING, handler=make_isr(handle_c))


def light_to_contrast(light):
    return MIN_CONTRAST + (MAX_CONTRAST - MIN_CONTRAST) * light // 4095


def put_text(s, x, y):
    # Draw text at (x, y) with the active scroll offset, wrapping around all
    # four screen edges so tilting scrolls content on/off smoothly.
    px = (x + scroll_x) % SCREEN_W
    py = (y + scroll_y) % SCREEN_H
    oled.text(s, px, py)
    # Second copy of the string for horizontal wrap-around.
    oled.text(s, px - SCREEN_W, py)
    # And again for vertical wrap, including the diagonal corner.
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


print("Lab 4 Checkpoint 1 - tilt-scrolled alarm clock")

last_second = -1
light = light_sensor.read()
contrast = light_to_contrast(light)
oled.contrast(contrast)

while True:
    # --- Tilt-driven scrolling ---
    ax, ay, _az = read_xyz()
    # Dominant principal direction only; diagonals pick the stronger axis.
    if abs(ax) > abs(ay):
        if ax > TILT_THRESHOLD:
            scroll_x = (scroll_x + SCROLL_STEP) % SCREEN_W
            needs_redraw = True
        elif ax < -TILT_THRESHOLD:
            scroll_x = (scroll_x - SCROLL_STEP) % SCREEN_W
            needs_redraw = True
    else:
        if ay > TILT_THRESHOLD:
            scroll_y = (scroll_y + SCROLL_STEP) % SCREEN_H
            needs_redraw = True
        elif ay < -TILT_THRESHOLD:
            scroll_y = (scroll_y - SCROLL_STEP) % SCREEN_H
            needs_redraw = True

    # --- Light-adaptive contrast ---
    smoothed = (1 - LIGHT_SMOOTHING) * light + LIGHT_SMOOTHING * light_sensor.read()
    light = round(smoothed)

    target = light_to_contrast(light)
    if (abs(target - contrast) >= CONTRAST_STEP
            or (target != contrast and target in (MIN_CONTRAST, MAX_CONTRAST))):
        contrast = target
        oled.contrast(contrast)

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

    if seconds != last_second or needs_redraw:
        last_second = seconds
        needs_redraw = False
        draw(hours, minutes, seconds, light, contrast)

    time.sleep_ms(20)
