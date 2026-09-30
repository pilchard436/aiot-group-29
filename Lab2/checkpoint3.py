from machine import Pin, ADC, PWM
import time
from button_debounce import read_button, setup_button

# The button is active-low: released = HIGH, pressed = LOW.
button = Pin(27, Pin.IN, Pin.PULL_UP)
setup_button(button)

# Part 1 hardware: PWM LED, PWM piezo, and analog light sensor.
led = PWM(Pin(13))
led.freq(1000)
piezo = PWM(Pin(12))
piezo.duty_u16(0)

light_sensor = ADC(Pin(36))
light_sensor.atten(ADC.ATTN_11DB)
light_sensor.width(ADC.WIDTH_12BIT)

print("Checkpoint 3")

while True:
    button_state = read_button()

    if button_state == 0:
        sensor_value = light_sensor.read()  # 0..4095

        # Map the light level to LED brightness.
        brightness = int((sensor_value / 4095) * 65535)
        led.duty_u16(brightness)

        # Map the light level to pitch: darker light produces a higher pitch.
        pitch = 200 + int((4095 - sensor_value) / 4095 * 1800)
        piezo.freq(pitch)
        piezo.duty_u16(32768)
    else:
        # Releasing the button turns off both outputs.
        led.duty_u16(0)
        piezo.duty_u16(0)

    time.sleep_ms(1)
