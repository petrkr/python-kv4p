#!/usr/bin/env python3
"""Example: transmit a WAV file as TX audio.

Requires the radio's firmware to be on the OPUS TX audio path (see
Kv4pRadio.codec). The WAV file must be 48 kHz mono 16-bit PCM.

Needs the ``opuslib`` package (not a python-kv4p dependency):

    pip install opuslib
"""

import argparse
import sys
import wave

try:
    import opuslib
except ImportError:
    sys.exit("need this library: pip install opuslib")

from kv4p import Kv4pRadio
from kv4p.transports.serial import Kv4pSerialTransport

OPUS_SAMPLE_RATE = 48000
OPUS_FRAME_SAMPLES = 1920  # 40 ms at 48 kHz


def encode_wav_to_opus_packets(path: str) -> list[bytes]:
    """Read a 48 kHz mono 16-bit WAV file and encode it into raw Opus packets."""
    with wave.open(path, "rb") as wav_file:
        if wav_file.getframerate() != OPUS_SAMPLE_RATE or wav_file.getnchannels() != 1 or wav_file.getsampwidth() != 2:
            raise ValueError("WAV file must be 48 kHz, mono, 16-bit PCM")
        pcm = wav_file.readframes(wav_file.getnframes())

    encoder = opuslib.Encoder(OPUS_SAMPLE_RATE, 1, opuslib.APPLICATION_VOIP)
    frame_bytes = OPUS_FRAME_SAMPLES * 2  # 16-bit mono

    packets = []
    for offset in range(0, len(pcm), frame_bytes):
        frame = pcm[offset:offset + frame_bytes]
        if len(frame) < frame_bytes:
            frame = frame + b"\x00" * (frame_bytes - len(frame))
        packets.append(encoder.encode(frame, OPUS_FRAME_SAMPLES))
    return packets


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("wav_file", help="48 kHz mono 16-bit WAV file to transmit")
parser.add_argument("--device", default="/dev/ttyUSB0", help="serial device (default: %(default)s)")
args = parser.parse_args()

packets = encode_wav_to_opus_packets(args.wav_file)
print(f"Encoded {len(packets)} Opus packets")

transport = Kv4pSerialTransport(args.device, 115200)
radio = Kv4pRadio(transport)

radio.connect()
try:
    print(f"Connected to firmware {radio.hello.version.ver}")
    radio.set_tx_allowed(True)

    print("Transmitting...")
    radio.set_ptt(True)
    try:
        for packet in packets:
            radio.send_tx_audio(packet)
        radio.flush()
    finally:
        radio.set_ptt(False)
    print("Done.")
finally:
    radio.disconnect()
