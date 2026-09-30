import time


_button = None
_debounce_ms = 10
_button_state = 1
_pending_state = 1
_last_edge_ms = 0


def _button_isr(pin):
    global _pending_state, _last_edge_ms

    # Record the edge in the ISR; debounce it in read_button().
    _pending_state = pin.value()
    _last_edge_ms = time.ticks_ms()


def setup_button(button, debounce_ms=10):
    """Configure a button pin and return its initial stable state."""
    global _button, _debounce_ms, _button_state, _pending_state, _last_edge_ms

    _button = button
    _debounce_ms = debounce_ms
    _button_state = button.value()
    _pending_state = _button_state
    _last_edge_ms = time.ticks_ms()
    button.irq(
        trigger=button.IRQ_FALLING | button.IRQ_RISING,
        handler=_button_isr,
    )
    return _button_state


def read_button():
    """Return the latest debounced electrical state of the button."""
    global _button_state

    if _button is None:
        raise RuntimeError("Call setup_button() before read_button()")

    if _pending_state != _button_state:
        if time.ticks_diff(time.ticks_ms(), _last_edge_ms) >= _debounce_ms:
            _button_state = _pending_state

    return _button_state