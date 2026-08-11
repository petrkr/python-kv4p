"""Tests for vendor payload encoding/decoding."""

import pytest

from kv4p import decode_vendor_payload, encode_vendor_payload


class TestVendorPayload:
    """Unit tests for vendor payload encode/decode."""

    def test_encode_empty_payload(self):
        """Encode vendor payload with no data."""
        result = encode_vendor_payload(0x0D)
        assert result.startswith(b"KV4P")
        assert result[5] == 0x0D

    def test_encode_with_data(self):
        """Encode vendor payload with data."""
        data = b"\x01\x02\x03"
        result = encode_vendor_payload(0x0D, data)
        assert result.startswith(b"KV4P")
        assert result[5] == 0x0D
        assert result[6:] == data

    def test_decode_valid_payload(self):
        """Decode valid vendor payload."""
        encoded = encode_vendor_payload(0x0D, b"\x01\x02\x03")
        command, payload = decode_vendor_payload(encoded)
        assert command == 0x0D
        assert payload == b"\x01\x02\x03"

    def test_decode_empty_payload(self):
        """Decode vendor payload with no data."""
        encoded = encode_vendor_payload(0x0D)
        command, payload = decode_vendor_payload(encoded)
        assert command == 0x0D
        assert payload == b""

    def test_decode_invalid_prefix(self):
        """Decode payload with wrong prefix."""
        result = decode_vendor_payload(b"XXXX\x01\x0D")
        assert result is None

    def test_decode_too_short(self):
        """Decode payload that's too short."""
        result = decode_vendor_payload(b"KV")
        assert result is None

    def test_decode_wrong_version(self):
        """Decode payload with wrong protocol version."""
        result = decode_vendor_payload(b"KV4P\x02\x0D")
        assert result is None
