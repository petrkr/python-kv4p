"""Tests for message parsing (Version, DeviceState)."""

import struct

import pytest

from kv4p.messages.device_state import DeviceState
from kv4p.messages.version import Version


class TestVersionParsing:
    """Unit tests for Version message parsing."""

    def test_parse_version(self):
        """Test parsing valid Version payload."""
        # Struct: <HcIBffB (2 + 1 + 4 + 1 + 4 + 4 + 1 = 17 bytes)
        data = struct.pack("<HcIBffB", 17, b"D", 2048, 0, 134.0, 174.0, 0)
        version = Version.from_bytes(data)

        assert version.ver == 17
        assert version.radio_module_status == "D"
        assert version.window_size == 2048
        assert version.rf_module_type == 0
        assert version.min_radio_freq == 134.0
        assert version.max_radio_freq == 174.0
        assert version.features == 0

    def test_version_payload_too_short(self):
        """Test that short payload raises ValueError."""
        with pytest.raises(ValueError):
            Version.from_bytes(b"short")


class TestDeviceStateParsing:
    """Unit tests for DeviceState message parsing."""

    def test_parse_device_state(self):
        """Test parsing valid DeviceState payload."""
        # Struct: <IiHBffBBBcBBB (4 + 4 + 2 + 1 + 4 + 4 + 1 + 1 + 1 + 1 + 1 + 1 + 1 = 26 bytes)
        data = struct.pack(
            "<IiHBffBBBcBBB",
            0,      # applied_sequence
            -1,     # memory_id
            0,      # flags
            0,      # bw
            145.500,  # freq_tx
            145.500,  # freq_rx
            0,      # ctcss_tx
            1,      # squelch
            0,      # ctcss_rx
            b"D",    # radio_module_status
            1,      # mode
            0,      # last_error
            0,      # latest_rssi
        )
        state = DeviceState.from_bytes(data)

        assert state.applied_sequence == 0
        assert state.memory_id == -1
        assert state.flags == 0
        assert state.bw == 0
        assert state.freq_tx == 145.500
        assert state.freq_rx == 145.500
        assert state.ctcss_tx == 0
        assert state.squelch == 1
        assert state.ctcss_rx == 0
        assert state.mode == 1

    def test_device_state_payload_too_short(self):
        """Test that short payload raises ValueError."""
        with pytest.raises(ValueError):
            DeviceState.from_bytes(b"short")
