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
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
OPENWEATHER_API_KEY = "d781378b14840cde07aec5d481840881"


# Feather ESP32 V2 OLED FeatherWing: SCL = GPIO 20, SDA = GPIO 22.
i2c = I2C(0, scl=Pin(20), sda=Pin(22), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 32, i2c)


def show_lines(*lines):
    oled.fill(0)
    for row, line in enumerate(lines[:4]):
        oled.text(str(line)[:16], 0, row * 8)
    oled.show()


def show_error(error):
    message = str(error)
    if " HTTP " in message:
        service, status = message.rsplit(" HTTP ", 1)
        show_lines("Weather error", service, "HTTP {}".format(status))
    else:
        show_lines(
            "Weather error",
            message[:16],
            message[16:32],
            message[32:48],
        )


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        start_ms = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), start_ms) >= WIFI_TIMEOUT_MS:
                raise OSError("Timed out connecting to Wi-Fi")
            time.sleep_ms(250)
    return wlan


def get_json(url, service_name):
    response = urequests.get(url)
    try:
        if response.status_code != 200:
            raise OSError("{} HTTP {}".format(service_name, response.status_code))
        data = ujson.loads(response.text)
    finally:
        response.close()

    if not isinstance(data, dict):
        raise ValueError("{} returned invalid data".format(service_name))
    return data


def get_coordinates():
    data = get_json(GEOLOCATION_URL, "Geolocation API")
    if data.get("status") != "success":
        raise OSError("Geolocation API: {}".format(
            data.get("message", "request failed")))

    latitude = data.get("lat")
    longitude = data.get("lon")
    if (not isinstance(latitude, (int, float))
            or not isinstance(longitude, (int, float))):
        raise ValueError("Geolocation response has no coordinates")
    return latitude, longitude


def get_weather(latitude, longitude):
    if (not OPENWEATHER_API_KEY
            or OPENWEATHER_API_KEY == "YOUR_OPENWEATHER_API_KEY"):
        raise ValueError("Set OPENWEATHER_API_KEY before running this script")

    url = "{}?lat={}&lon={}&appid={}&units=metric".format(
        WEATHER_URL, latitude, longitude, OPENWEATHER_API_KEY)
    data = get_json(url, "Weather API")

    measurements = data.get("main")
    conditions = data.get("weather")
    if not isinstance(measurements, dict) or not isinstance(conditions, list):
        raise ValueError("Weather response is missing current conditions")
    if not conditions or not isinstance(conditions[0], dict):
        raise ValueError("Weather response has no description")

    temperature = measurements.get("temp")
    description = conditions[0].get("description")
    if (not isinstance(temperature, (int, float))
            or not isinstance(description, str)):
        raise ValueError("Weather response has invalid conditions")
    return temperature, description


def main():
    try:
        connect_wifi()
        latitude, longitude = get_coordinates()
        temperature, description = get_weather(latitude, longitude)
    except (OSError, ValueError) as error:
        show_error(error)
        print("Weather error:", error)
        raise

    show_lines(
        "Current weather",
        "Temp: {:.1f} C".format(temperature),
        description,
    )
    print("Coordinates: {:.5f}, {:.5f}".format(latitude, longitude))
    print("Temperature: {:.1f} C".format(temperature))
    print("Description: {}".format(description))


print("Checkpoint 3 - Part 2 Task 3")
main()