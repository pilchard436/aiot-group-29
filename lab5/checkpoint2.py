import network
import neopixel
import socket
import time
import ujson
import urequests
import uselect
from machine import I2C, Pin, PWM, RTC
import ssd1306


WIFI_SSID = "Columbia University"
WIFI_PASSWORD = ""
WIFI_TIMEOUT_MS = 15000
SERVER_PORT = 8080
MAX_COMMAND_BYTES = 512
GEOLOCATION_URL = "http://ip-api.com/json"
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
OPENWEATHER_API_KEY = "d781378b14840cde07aec5d481840881"

DISPLAY_ON = 0xAF
DISPLAY_OFF = 0xAE
ALARM_COLOR = (64, 0, 0)
RING_TOGGLE_MS = 250
RING_TIMEOUT_MS = 60000


rtc = RTC()
i2c = I2C(0, scl=Pin(20), sda=Pin(22), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 32, i2c)

piezo = PWM(Pin(12))
piezo.freq(2000)
piezo.duty_u16(0)

neopixel_power = Pin(2, Pin.OUT)
neopixel_power.value(1)
alarm_led = neopixel.NeoPixel(Pin(0, Pin.OUT), 1)
alarm_led[0] = (0, 0, 0)
alarm_led.write()

alarm_hours = 0
alarm_minutes = 0
alarm_seconds = 0
alarm_enabled = False
alarm_fired = False
ringing = False
ring_start_ms = 0
ring_toggle_ms = 0
ring_on = False
clock_display_active = False
clock_last_second = -1


def _show_lines(*lines):
    oled.fill(0)
    for row, line in enumerate(lines[:4]):
        oled.text(str(line)[:16], 0, row * 8)
    oled.show()


def _wrap_message(message):
    lines = []
    for paragraph in message.splitlines() or [""]:
        words = paragraph.split()
        line = ""
        for word in words:
            while len(word) > 16:
                if line:
                    lines.append(line)
                    line = ""
                lines.append(word[:16])
                word = word[16:]
            if not word:
                continue
            if line and len(line) + len(word) + 1 > 16:
                lines.append(line)
                line = word
            elif line:
                line += " " + word
            else:
                line = word
        if line:
            lines.append(line)
        elif not words:
            lines.append("")
    return lines[:4]


def screen_on():
    """Turn on the OLED display."""
    oled.write_cmd(DISPLAY_ON)
    return "Screen on"


def screen_off():
    """Turn off the OLED display."""
    global clock_display_active
    clock_display_active = False
    oled.write_cmd(DISPLAY_OFF)
    return "Screen off"


def _draw_clock(force=False):
    global clock_last_second
    year, month, day, weekday, hours, minutes, seconds, _ = rtc.datetime()
    days = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    if force or seconds != clock_last_second:
        screen_on()
        _show_lines(
            "Time {:02d}:{:02d}:{:02d}".format(hours, minutes, seconds),
            "{} {:04d}-{:02d}-{:02d}".format(
                days[weekday], year, month, day),
        )
        clock_last_second = seconds
    return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)


def display_time():
    """Start a live clock display; takes no arguments."""
    global clock_display_active, clock_last_second
    clock_display_active = True
    clock_last_second = -1
    return _draw_clock(force=True)


def service_clock():
    """Refresh the live clock when its displayed second changes."""
    if clock_display_active:
        return _draw_clock()


def display_message(message):
    """Show a text message on the OLED; args: [message]."""
    global clock_display_active
    if not isinstance(message, str):
        raise TypeError("message must be text")
    clock_display_active = False
    screen_on()
    _show_lines(*_wrap_message(message))
    return message


def _set_ring_output(on):
    global ring_on
    ring_on = on
    piezo.duty_u16(32768 if on else 0)
    alarm_led[0] = ALARM_COLOR if on else (0, 0, 0)
    alarm_led.write()


def stop_alarm():
    """Stop an active alarm."""
    global ringing
    ringing = False
    _set_ring_output(False)
    return "Alarm stopped"


def set_alarm(hour, minute, second):
    """Set a daily alarm; args: [hour (0-23), minute (0-59), second (0-59)]."""
    global alarm_hours, alarm_minutes, alarm_seconds
    global alarm_enabled, alarm_fired, clock_display_active
    if type(hour) is not int:
        raise TypeError("hour must be an integer")
    if type(minute) is not int:
        raise TypeError("minute must be an integer")
    if type(second) is not int:
        raise TypeError("second must be an integer")
    if not 0 <= hour < 24:
        raise ValueError("hour must be from 0 to 23")
    if not 0 <= minute < 60:
        raise ValueError("minute must be from 0 to 59")
    if not 0 <= second < 60:
        raise ValueError("second must be from 0 to 59")

    if ringing:
        stop_alarm()
    alarm_hours = hour
    alarm_minutes = minute
    alarm_seconds = second
    alarm_enabled = True
    alarm_fired = False
    clock_display_active = False
    screen_on()
    _show_lines("Alarm set", "{:02d}:{:02d}:{:02d}".format(
        hour, minute, second))
    return "Alarm set for {:02d}:{:02d}:{:02d}".format(
        hour, minute, second)


def service_alarm():
    """Poll the alarm; call regularly from the smartwatch server loop."""
    global alarm_fired, ringing, ring_start_ms, ring_toggle_ms
    global clock_display_active
    now = rtc.datetime()
    at_alarm_time = (now[4] == alarm_hours
                     and now[5] == alarm_minutes
                     and now[6] == alarm_seconds)

    if not at_alarm_time:
        alarm_fired = False
    elif alarm_enabled and not alarm_fired and not ringing:
        alarm_fired = True
        ringing = True
        clock_display_active = False
        ring_start_ms = time.ticks_ms()
        ring_toggle_ms = ring_start_ms
        _set_ring_output(True)
        screen_on()
        _show_lines("ALARM!", "{:02d}:{:02d}:{:02d}".format(
            alarm_hours, alarm_minutes, alarm_seconds))

    if ringing:
        current_ms = time.ticks_ms()
        if time.ticks_diff(current_ms, ring_start_ms) >= RING_TIMEOUT_MS:
            stop_alarm()
        elif time.ticks_diff(current_ms, ring_toggle_ms) >= RING_TOGGLE_MS:
            ring_toggle_ms = current_ms
            _set_ring_output(not ring_on)


def _connect_wifi():
    if not WIFI_SSID or WIFI_SSID == "YOUR_WIFI_SSID":
        raise ValueError("Set WIFI_SSID before requesting location or weather")

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


def _get_json(url, service_name):
    response = urequests.get(url)
    try:
        if response.status_code != 200:
            raise OSError("{} HTTP {}".format(
                service_name, response.status_code))
        data = ujson.loads(response.text)
    finally:
        response.close()
    if not isinstance(data, dict):
        raise ValueError("{} returned invalid data".format(service_name))
    return data


def _get_coordinates():
    data = _get_json(GEOLOCATION_URL, "Geolocation API")
    if data.get("status") != "success":
        raise OSError("Geolocation API: {}".format(
            data.get("message", "request failed")))

    latitude = data.get("lat")
    longitude = data.get("lon")
    if (not isinstance(latitude, (int, float))
            or not isinstance(longitude, (int, float))):
        raise ValueError("Geolocation response has no coordinates")
    return latitude, longitude


def display_location():
    """Show the current network location; takes no arguments."""
    global clock_display_active
    _connect_wifi()
    latitude, longitude = _get_coordinates()
    clock_display_active = False
    screen_on()
    _show_lines(
        "Your coordinates",
        "Lat: {:.5f}".format(latitude),
        "Lon: {:.5f}".format(longitude),
    )
    return "{:.5f}, {:.5f}".format(latitude, longitude)


def display_weather():
    """Show current local weather; takes no arguments."""
    global clock_display_active
    if (not OPENWEATHER_API_KEY
            or OPENWEATHER_API_KEY == "YOUR_OPENWEATHER_API_KEY"):
        raise ValueError("Set OPENWEATHER_API_KEY before requesting weather")

    _connect_wifi()
    latitude, longitude = _get_coordinates()
    url = "{}?lat={}&lon={}&appid={}&units=metric".format(
        WEATHER_URL, latitude, longitude, OPENWEATHER_API_KEY)
    data = _get_json(url, "Weather API")
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
    clock_display_active = False
    screen_on()
    _show_lines(
        "Current weather",
        "Temp: {:.1f} C".format(temperature),
        description,
    )
    return "{:.1f} C, {}".format(temperature, description)


WATCH_FUNCTIONS = {
    "screen_on": screen_on,
    "screen_off": screen_off,
    "display_time": display_time,
    "display_message": display_message,
    "set_alarm": set_alarm,
    "display_location": display_location,
    "display_weather": display_weather,
}


def execute_command(request):
    """Validate and invoke one {name, args} smartwatch command."""
    if not isinstance(request, dict):
        raise ValueError("Command must be a JSON object")
    if "name" not in request or "args" not in request:
        raise ValueError("Command must contain name and args")

    name = request["name"]
    args = request["args"]
    if not isinstance(name, str):
        raise ValueError("Command name must be text")
    if not isinstance(args, list):
        raise ValueError("Command args must be a JSON array")
    if name not in WATCH_FUNCTIONS:
        raise ValueError("Unknown command: {}".format(name))

    return WATCH_FUNCTIONS[name](*args)


def _receive_command(client):
    data = bytearray()
    while True:
        chunk = client.recv(min(128, MAX_COMMAND_BYTES + 1 - len(data)))
        if not chunk:
            break

        newline = chunk.find(b"\n")
        if newline >= 0:
            data.extend(chunk[:newline])
            if chunk[newline + 1:].strip():
                raise ValueError("Send only one command per connection")
            break

        data.extend(chunk)
        if len(data) > MAX_COMMAND_BYTES:
            raise ValueError("Command exceeds {} bytes".format(
                MAX_COMMAND_BYTES))

    command = data.decode().strip()
    if not command:
        raise ValueError("No JSON command received")
    return command


def _send_response(client, response):
    data = (ujson.dumps(response) + "\n").encode()
    sent = 0
    while sent < len(data):
        count = client.send(data[sent:])
        if count <= 0:
            raise OSError("Connection closed while sending response")
        sent += count


def _handle_client(client, address):
    try:
        client.settimeout(5)
        command = ujson.loads(_receive_command(client))
        response = {"ok": True, "result": execute_command(command)}
    except (ValueError, TypeError, OSError) as error:
        response = {"ok": False, "error": str(error)}
        print("Command error from {}: {}".format(address, error))

    try:
        _send_response(client, response)
    except OSError as error:
        print("Response error to {}: {}".format(address, error))
    finally:
        try:
            client.close()
        except OSError as error:
            print("Socket close error for {}: {}".format(address, error))


def serve_forever(port=SERVER_PORT):
    """Serve newline-terminated JSON commands over TCP on the ESP32."""
    wlan = _connect_wifi()
    server = socket.socket()
    try:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", port))
        server.listen(1)

        poller = uselect.poll()
        poller.register(server, uselect.POLLIN)
        print("Smartwatch server listening on {}:{}".format(
            wlan.ifconfig()[0], port))

        while True:
            service_alarm()
            service_clock()
            if poller.poll(100):
                client, address = server.accept()
                _handle_client(client, address)
    finally:
        server.close()


serve_forever()