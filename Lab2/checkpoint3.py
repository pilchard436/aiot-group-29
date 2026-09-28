from machine import Pin, ADC, PWM
import time

# The button is active-low: released = HIGH, pressed = LOW.
button = Pin(27, Pin.IN, Pin.PULL_UP)

# Part 1 hardware: PWM LED, PWM piezo, and analog light sensor.
led = PWM(Pin(13))
led.freq(1000)
piezo = PWM(Pin(12))
piezo.duty_u16(0)

light_sensor = ADC(Pin(36))
light_sensor.atten(ADC.ATTN_11DB)
light_sensor.width(ADC.WIDTH_12BIT)

button_state = button.value()
pending_state = button_state
last_edge_ms = time.ticks_ms()


def button_isr(pin):
    global pending_state, last_edge_ms

    # The ISR records the edge only. Debouncing is completed in the main loop
    # after the input has remained unchanged for 10 ms.
    pending_state = pin.value()
    last_edge_ms = time.ticks_ms()


button.irq(
    trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING,
    handler=button_isr,
)

print("Checkpoint 3")

while True:
    # Confirm both press and release only after the signal has been stable.
    if pending_state != button_state:
        if time.ticks_diff(time.ticks_ms(), last_edge_ms) >= 10:
            button_state = pending_state

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
