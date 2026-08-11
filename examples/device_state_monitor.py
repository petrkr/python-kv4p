#!/usr/bin/env python3
"""Example: monitor device state updates with flags."""

from kv4p import (
    Kv4pRadio,
    HOST_STATE_HIGH_POWER,
    HOST_STATE_TX_ALLOWED,
    HOST_STATE_RX_AUDIO_OPEN,
)
from kv4p.transports.serial import Kv4pSerialTransport

transport = Kv4pSerialTransport("/dev/ttyUSB0", 115200)
radio = Kv4pRadio(transport)

# Register device state callback
def on_device_state(state):
    """Called when firmware sends periodic device state updates."""
    # Extract selected flags
    high_power = bool(state.flags & HOST_STATE_HIGH_POWER)
    tx_allowed = bool(state.flags & HOST_STATE_TX_ALLOWED)
    rx_audio = bool(state.flags & HOST_STATE_RX_AUDIO_OPEN)

    # Mode names
    mode_names = {0: "TX", 1: "RX", 2: "STOPPED"}
    mode_name = mode_names.get(state.mode, f"UNKNOWN({state.mode})")

    print(f"[State] "
          f"Mode: {mode_name}, "
          f"Freq RX: {state.freq_rx:.3f} MHz, "
          f"TX: {state.freq_tx:.3f} MHz, "
          f"Squelch: {state.squelch}, "
          f"RSSI: {state.latest_rssi} dBm, "
          f"HighPower: {high_power}, "
          f"TX_OK: {tx_allowed}, "
          f"RX_Audio: {rx_audio}, "
          f"Flags: {state.flags}")


def on_sql_change(open_: bool):
    """Called when squelch opens or closes."""
    status = "OPEN" if open_ else "CLOSED"
    print(f"[SQL] Squelch {status}")


radio.on_device_state(on_device_state)

# Connect and monitor
radio.connect()
try:
    print(f"Connected to firmware {radio.hello.version.ver}")
    print("Enabling status reports...")
    radio.set_status_reports(True)
    radio.set_rx_audio_open(True)
    radio.on_sql(on_sql_change)

    print("Monitoring device state (Ctrl+C to exit)...")

    import time
    while True:
        time.sleep(1)
finally:
    radio.disconnect()
