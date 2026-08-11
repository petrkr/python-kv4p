"""Tests for KISS protocol framing."""

from kv4p.constants.kiss import KISS_FEND, KISS_FESC, KISS_TFEND, KISS_TFESC
from kv4p.protocol.kiss import KissParser, encode_kiss_frame


class TestEncodeKissFrame:
    """Unit tests for KISS frame encoding."""

    def test_encode_simple(self):
        """Encode simple frame without escaping."""
        result = encode_kiss_frame(0x0D, b"hello")
        expected = KISS_FEND.to_bytes(1) + b"\x0dhello" + KISS_FEND.to_bytes(1)
        assert result == expected

    def test_encode_empty_payload(self):
        """Encode frame with no payload."""
        result = encode_kiss_frame(0x0D, b"")
        expected = KISS_FEND.to_bytes(1) + b"\x0d" + KISS_FEND.to_bytes(1)
        assert result == expected

    def test_encode_with_fend_escape(self):
        """Encode payload containing FEND byte."""
        payload = bytes([0x01, KISS_FEND, 0x02])
        result = encode_kiss_frame(0x0D, payload)
        # KISS_FEND in payload should be escaped as FESC + TFEND
        assert KISS_FESC in result
        assert KISS_TFEND in result

    def test_encode_with_fesc_escape(self):
        """Encode payload containing FESC byte."""
        payload = bytes([0x01, KISS_FESC, 0x02])
        result = encode_kiss_frame(0x0D, payload)
        # KISS_FESC in payload should be escaped as FESC + TFESC
        assert KISS_TFESC in result  # escape indicator for FESC

    def test_encode_with_both_escapes(self):
        """Encode payload with both FEND and FESC."""
        payload = bytes([KISS_FEND, KISS_FESC])
        result = encode_kiss_frame(0x0D, payload)
        # Should have frame delimiters at start and end
        assert result[0] == KISS_FEND
        assert result[-1] == KISS_FEND


class TestKissParser:
    """Unit tests for KISS frame parser."""

    def test_parse_simple_frame(self):
        """Parse simple frame without escaping."""
        frames = []
        parser = KissParser(lambda cmd, payload: frames.append((cmd, payload)))

        data = KISS_FEND.to_bytes(1) + b"\x0dhello" + KISS_FEND.to_bytes(1)
        parser.feed(data)

        assert len(frames) == 1
        assert frames[0] == (0x0d, b"hello")

    def test_parse_empty_payload(self):
        """Parse frame with no payload."""
        frames = []
        parser = KissParser(lambda cmd, payload: frames.append((cmd, payload)))

        data = KISS_FEND.to_bytes(1) + b"\x0d" + KISS_FEND.to_bytes(1)
        parser.feed(data)

        assert len(frames) == 1
        assert frames[0] == (0x0d, b"")

    def test_parse_with_escape_fend(self):
        """Parse frame with escaped FEND in payload."""
        frames = []
        parser = KissParser(lambda cmd, payload: frames.append((cmd, payload)))

        # Payload: 0x01, FEND (escaped), 0x02
        data = bytearray([KISS_FEND, 0x0d, 0x01])
        data.extend([KISS_FESC, KISS_TFEND])
        data.extend([0x02, KISS_FEND])
        parser.feed(bytes(data))

        assert len(frames) == 1
        assert frames[0][0] == 0x0d
        assert frames[0][1] == bytes([0x01, KISS_FEND, 0x02])

    def test_parse_with_escape_fesc(self):
        """Parse frame with escaped FESC in payload."""
        frames = []
        parser = KissParser(lambda cmd, payload: frames.append((cmd, payload)))

        # Payload: 0x01, FESC (escaped), 0x02
        data = bytearray([KISS_FEND, 0x0d, 0x01])
        data.extend([KISS_FESC, KISS_TFESC])
        data.extend([0x02, KISS_FEND])
        parser.feed(bytes(data))

        assert len(frames) == 1
        assert frames[0][0] == 0x0d
        assert frames[0][1] == bytes([0x01, KISS_FESC, 0x02])

    def test_parse_multiple_frames(self):
        """Parse multiple frames."""
        frames = []
        parser = KissParser(lambda cmd, payload: frames.append((cmd, payload)))

        # Two simple frames
        data = (
            KISS_FEND.to_bytes(1) + b"\x0dframe1" + KISS_FEND.to_bytes(1)
            + KISS_FEND.to_bytes(1) + b"\x0eframe2" + KISS_FEND.to_bytes(1)
        )
        parser.feed(data)

        assert len(frames) == 2
        assert frames[0] == (0x0d, b"frame1")
        assert frames[1] == (0x0e, b"frame2")

    def test_parse_bytes_outside_frame_ignored(self):
        """Test that bytes outside frame delimiter are ignored."""
        frames = []
        parser = KissParser(lambda cmd, payload: frames.append((cmd, payload)))

        # Garbage before first FEND
        data = b"garbage" + KISS_FEND.to_bytes(1) + b"\x0dvalid" + KISS_FEND.to_bytes(1)
        parser.feed(data)

        assert len(frames) == 1
        assert frames[0] == (0x0d, b"valid")

    def test_parse_invalid_escape_sequence(self):
        """Test handling of invalid escape sequence."""
        frames = []
        parser = KissParser(lambda cmd, payload: frames.append((cmd, payload)))

        # Invalid escape: FESC followed by invalid byte (not TFEND or TFESC)
        data = bytearray([KISS_FEND, 0x0d, 0x01])
        data.extend([KISS_FESC, 0xFF])  # invalid escape byte
        data.extend([0x02, KISS_FEND])
        parser.feed(bytes(data))

        assert len(frames) == 1
        # Invalid escape byte should be ignored
        assert frames[0][1] == bytes([0x01, 0x02])
