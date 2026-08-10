"""KV4P vendor envelope constants."""

from __future__ import annotations

KV4P_PROTOCOL_VERSION = 0x01
KV4P_VENDOR_PREFIX = b"KV4P"
KV4P_VENDOR_HEADER_LEN = 6

# Audio payload, same command code in both directions (host->device TX,
# device->host RX) depending on which codec the firmware uses.
COMMAND_AUDIO_OPUS = 0x07
COMMAND_AUDIO_ADPCM = 0x0C

# Host -> device
COMMAND_HOST_DESIRED_STATE = 0x0D

# Device -> host
COMMAND_DEBUG_INFO = 0x01
COMMAND_DEBUG_ERROR = 0x02
COMMAND_DEBUG_WARN = 0x03
COMMAND_DEBUG_DEBUG = 0x04
COMMAND_DEBUG_TRACE = 0x05
COMMAND_HELLO = 0x06
COMMAND_WINDOW_UPDATE = 0x09
COMMAND_DEVICE_STATE = 0x0B
