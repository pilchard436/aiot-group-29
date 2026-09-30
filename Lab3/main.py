from machine import RTC, I2C, Pin
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

print("Checkpoint 1 - Part 2 Task 2")

last_second = -1

while True:
    year, month, day, weekday, hours, minutes, seconds, _ = rtc.datetime()

    # Redraw only when the second changes to avoid needless I2C traffic.
    if seconds != last_second:
        last_second = seconds
        oled.fill(0)
        oled.text("{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds), 0, 0)
        oled.text("{} {:04d}-{:02d}-{:02d}".format(
            DAYS[weekday], year, month, day), 0, 12)
        oled.show()

    time.sleep_ms(50)
