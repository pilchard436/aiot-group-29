import network
import time
import ujson
import urequests
from machine import I2C, Pin
import ssd1306


WIFI_SSID = "Columbia University"
WIFI_PASSWORD = ""
WIFI_TIMEOUT_MS = 15000
GEOLOCATION_URL = "http://ip-api.com/json"


# Feather ESP32 V2 OLED FeatherWing: SCL = GPIO 20, SDA = GPIO 22.
i2c = I2C(0, scl=Pin(20), sda=Pin(22), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 32, i2c)


def show_lines(*lines):
    oled.fill(0)
    for row, line in enumerate(lines[:4]):
        oled.text(str(line)[:16], 0, row * 8)
    oled.show()


def connect_wifi():
    if not WIFI_SSID or WIFI_SSID == "YOUR_WIFI_SSID":
        show_lines("Configure Wi-Fi", "SSID in script")
        raise ValueError("Set WIFI_SSID before running this script")

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        start_ms = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), start_ms) >= WIFI_TIMEOUT_MS:
                show_lines("Wi-Fi connection", "timed out")
                raise OSError("Timed out connecting to Wi-Fi")
            time.sleep_ms(250)
    return wlan


def get_coordinates():
    response = urequests.get(GEOLOCATION_URL)
    try:
        if response.status_code != 200:
            raise OSError("Geolocation API HTTP {}".format(response.status_code))
        data = ujson.loads(response.text)
    finally:
        response.close()

    if not isinstance(data, dict):
        raise ValueError("Invalid geolocation API response")
    if data.get("status") != "success":
        raise OSError("Geolocation API: {}".format(data.get("message", "request failed")))

    latitude = data.get("lat")
    longitude = data.get("lon")
    if (not isinstance(latitude, (int, float))
            or not isinstance(longitude, (int, float))):
        raise ValueError("Geolocation response has no coordinates")
    return latitude, longitude


def main():
    try:
        connect_wifi()
        latitude, longitude = get_coordinates()
    except (OSError, ValueError) as error:
        show_lines("Location error", str(error))
        print("Location error:", error)
        raise

    show_lines(
        "Your coordinates",
        "Lat: {:.5f}".format(latitude),
        "Lon: {:.5f}".format(longitude),
    )
    print("Latitude: {:.5f}".format(latitude))
    print("Longitude: {:.5f}".format(longitude))


print("Checkpoint 2 - Part 2 Task 2")
main()