# Lab 4 - Checkpoint 1
# Press button A to push the latest coordinates and weather to an ntfy.sh
# topic. Everything else (Wi-Fi, geolocation, weather) is reused from check3.

import time
import micropython
import urequests
from machine import Pin

from lab4_ok2373_yf2610_jz4215_check3 import (
    connect_wifi, get_coordinates, get_weather,
    show_lines, show_error,
)

NTFY_URL = "https://ntfy.sh/aiot_group29"

# === Buttons (OLED FeatherWing) ===
button_a = Pin(15, Pin.IN, Pin.PULL_UP)

DEBOUNCE_MS = 50

# Latest readings; filled in by main() before any button press matters.
latitude = 0.0
longitude = 0.0
temperature = 0.0
description = ""
have_data = False
push_pending = False


def push(_arg):
    global push_pending
    push_pending = False
    if not have_data:
        print("No weather data yet, skipping push")
        return
    body = "Lat: {:.5f}\nLon: {:.5f}\nTemp: {:.1f} C\n{}".format(
        latitude, longitude, temperature, description)
    try:
        response = urequests.post(NTFY_URL, data=body.encode("utf-8"))
        try:
            print("ntfy status:", response.status_code)
        finally:
            response.close()
    except OSError as error:
        print("ntfy error:", error)


def handle_a(_):
    # Fire-and-forget: schedule the HTTP POST out of the ISR so network I/O
    # does not run in interrupt context. Coalesce rapid presses.
    global push_pending
    if push_pending:
        return
    push_pending = True
    micropython.schedule(push, 0)


def make_isr(handler):
    last_press_ms = 0

    def isr(_):
        nonlocal last_press_ms
        now = time.ticks_ms()
        if time.ticks_diff(now, last_press_ms) < DEBOUNCE_MS:
            return
        last_press_ms = now
        handler(None)

    return isr


button_a.irq(trigger=Pin.IRQ_FALLING, handler=make_isr(handle_a))

def main():
    global latitude, longitude, temperature, description, have_data
    try:
        connect_wifi()
        latitude, longitude = get_coordinates()
        temperature, description = get_weather(latitude, longitude)
    except (OSError, ValueError) as error:
        show_error(error)
        print("Weather error:", error)
        raise

    have_data = True
    show_lines(
        "Lat: {:.5f}".format(latitude),
        "Lon: {:.5f}".format(longitude),
        "Temp: {:.1f} C".format(temperature),
        description,
    )
    print("Coordinates: {:.5f}, {:.5f}".format(latitude, longitude))
    print("Temperature: {:.1f} C".format(temperature))
    print("Description: {}".format(description))
    print("Press button A to push to", NTFY_URL)


print("Checkpoint 4 - Part 3")
main()

while True:
    time.sleep_ms(100)
