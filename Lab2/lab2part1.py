from machine import Pin, ADC, PWM
import time

# External LED on GPIO 13 using PWM
led = PWM(Pin(13))
led.freq(1000)

# Piezo buzzer on GPIO 12 using PWM
piezo = PWM(Pin(12))
piezo.freq(1000)

# Light sensor connected to A4 / GPIO 36
light_sensor = ADC(Pin(36))
light_sensor.atten(ADC.ATTN_11DB)
light_sensor.width(ADC.WIDTH_12BIT)

while True:
    sensor_value = light_sensor.read()  # 0..4095

    # Control LED brightness from light level
    brightness = int((sensor_value / 4095) * 65535)
    led.duty_u16(brightness)

    # Control piezo with light sensor: darker = louder, brighter = quieter
    if sensor_value < 2000:
        piezo.duty_u16(int((2000 - sensor_value) / 2000 * 30000))
    else:
        piezo.duty_u16(0)

    time.sleep_ms(100)  # 10 Hz sampling rate (100 ms per sample)
