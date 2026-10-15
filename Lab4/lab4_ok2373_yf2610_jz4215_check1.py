# Lab 4 - Checkpoint 1
# Lab 3 checkpoint 4 (alarm clock with light-adaptive OLED) + ADXL345 tilt
# scrolling. Everything clock-related is imported from alarm_clock; this file
# only adds the accelerometer and translates tilt into a scroll offset that
# alarm_clock honors when it draws.
#
# ADXL345 registers used:
#   0x00 DEVID       expect 0xE5
#   0x2C BW_RATE     0x0A -> 100 Hz output data rate
#   0x2D POWER_CTL   0x08 -> measure mode on
#   0x2E INT_ENABLE  0x00 -> no interrupts
#   0x31 DATA_FORMAT 0x00 -> +/-2g, right-justified, 10-bit
#   0x38 FIFO_CTL    0x00 -> bypass FIFO
#   0x32..0x37       X0,X1,Y0,Y1,Z0,Z1 data registers

from machine import Pin, SPI
import time

import alarm_clock

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

# At +/-2g, 10-bit right-justified -> 1 g ~= 256 LSB. ~0.3 g to trigger scroll.
TILT_THRESHOLD = 80
SCROLL_STEP = 2

print("Lab 4 Checkpoint 1 - tilt-scrolled alarm clock")

while True:
    ax, ay, _az = read_xyz()

    # Dominant principal axis only, so diagonals snap to one direction.
    scrolled = False
    if abs(ax) > abs(ay):
        if ax > TILT_THRESHOLD:
            alarm_clock.scroll_x = (alarm_clock.scroll_x + SCROLL_STEP) % alarm_clock.SCREEN_W
            scrolled = True
        elif ax < -TILT_THRESHOLD:
            alarm_clock.scroll_x = (alarm_clock.scroll_x - SCROLL_STEP) % alarm_clock.SCREEN_W
            scrolled = True
    else:
        if ay > TILT_THRESHOLD:
            alarm_clock.scroll_y = (alarm_clock.scroll_y + SCROLL_STEP) % alarm_clock.SCREEN_H
            scrolled = True
        elif ay < -TILT_THRESHOLD:
            alarm_clock.scroll_y = (alarm_clock.scroll_y - SCROLL_STEP) % alarm_clock.SCREEN_H
            scrolled = True

    # alarm_clock only redraws when the second changes or something internal
    # flagged it; nudging the scroll offset also needs a redraw.
    if scrolled:
        alarm_clock.request_redraw()

    alarm_clock.step()
    time.sleep_ms(20)
