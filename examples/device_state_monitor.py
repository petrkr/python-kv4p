#!/usr/bin/env python3
"""Example: monitor device state updates."""

from kv4p import Kv4pRadio
from kv4p.transports.serial import Kv4pSerialTransport

transport = Kv4pSerialTransport("/dev/ttyUSB0", 115200)
radio = Kv4pRadio(transport)

# Register device state callback
def on_device_state(state):
    """Called when firmware sends periodic device state updates."""
    print(f"[State] "
          f"Freq RX: {state.freq_rx:.3f} MHz, "
          f"TX: {state.freq_tx:.3f} MHz, "
          f"Squelch: {state.squelch}, "
          f"RSSI: {state.latest_rssi} dBm, "
          f"Mode: {state.mode}")

radio.on_device_state(on_device_state)

# Connect and monitor
radio.connect()
try:
    print(f"Connected to firmware {radio.hello.version.ver}")
    print("Enabling status reports...")
    radio.set_status_reports(True)
    print("Monitoring device state (Ctrl+C to exit)...")

    import time
    while True:
        time.sleep(1)
finally:
    radio.disconnect()
