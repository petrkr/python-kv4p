#!/usr/bin/env python3
"""Basic example: connect to radio and display firmware info and current settings."""

from kv4p import Kv4pRadio
from kv4p.transports.serial import Kv4pSerialTransport

transport = Kv4pSerialTransport("/dev/ttyUSB0", 115200)
radio = Kv4pRadio(transport)

radio.connect()

# After connect(), HELLO has been received and settings are seeded from firmware
hello = radio.hello
print(f"Firmware version: {hello.version.ver}")
print()

# Radio configuration properties
print("Current radio configuration:")
print(f"  RX Frequency: {radio.freq_rx:.3f} MHz")
print(f"  TX Frequency: {radio.freq_tx:.3f} MHz")
print(f"  Bandwidth: {radio.bandwidth}")
print(f"  Squelch: {radio.squelch}")
print(f"  RX CTCSS: {radio.ctcss_rx} Hz")
print(f"  TX CTCSS: {radio.ctcss_tx} Hz")
print()

# Radio capabilities and flags
print("Radio capabilities:")
print(f"  TX allowed: {radio.tx_allowed}")
print(f"  High power: {radio.high_power}")
print(f"  RSSI reporting: {radio.rssi}")
print(f"  RX audio open: {radio.rx_audio_open}")
print(f"  Status reports: {radio.status_reports}")
print(f"  Audio codec: {'OPUS' if radio.codec == 0x07 else 'ADPCM'}")
print()

# Audio filter settings
print("Audio filters:")
print(f"  Pre-emphasis: {radio.filter_pre}")
print(f"  High-pass: {radio.filter_high}")
print(f"  Low-pass: {radio.filter_low}")

radio.disconnect()
