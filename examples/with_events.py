#!/usr/bin/env python3
"""Example: register and handle events (SQL, physical PTT, AX.25 frames)."""

import argparse

from kv4p import Kv4pRadio
from kv4p.transports.serial import Kv4pSerialTransport

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--device", default="/dev/ttyUSB0", help="serial device (default: %(default)s)")
args = parser.parse_args()

transport = Kv4pSerialTransport(args.device, 115200)
radio = Kv4pRadio(transport)

# Register event callbacks
def on_sql_change(open_: bool):
    """Called when squelch opens or closes."""
    status = "OPEN" if open_ else "CLOSED"
    print(f"[SQL] Squelch {status}")

def on_phy_ptt_change(down: bool):
    """Called when the radio's physical PTT button is pressed or released."""
    status = "DOWN" if down else "UP"
    print(f"[PHY PTT] {status}")

def on_ax25_frame(payload: bytes):
    """Called when AX.25 frame is received."""
    print(f"[AX.25] Received {len(payload)} bytes: {payload.hex()}")

radio.on_sql(on_sql_change)
radio.on_phy_ptt(on_phy_ptt_change)
radio.on_ax25_frame(on_ax25_frame)

# Now connect and listen
radio.connect()
try:
    print(f"Connected to firmware {radio.hello.version.ver}")
    print(f"RX Frequency: {radio.freq_rx:.3f} MHz")

    radio.set_rx_audio_open(True)
    print("Listening for events (Ctrl+C to exit)...")


    # Keep running until interrupted
    import time
    while True:
        time.sleep(1)
finally:
    radio.disconnect()
