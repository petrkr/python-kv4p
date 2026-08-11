"""Integration tests for Kv4pRadio with DummyTransport."""

import pytest

from kv4p import Kv4pRadio, RadioNotReadyError
from kv4p.transports.dummy import DummyTransport


class TestRadioWithDummy:
    """Integration tests using DummyTransport (no hardware)."""

    def test_connect_and_hello(self):
        """Test that connect() receives HELLO."""
        transport = DummyTransport()
        radio = Kv4pRadio(transport)

        radio.connect()
        assert radio.is_ready
        assert radio.hello is not None
        assert radio.hello.version.ver == 17
        radio.disconnect()

    def test_context_manager(self):
        """Test context manager automatically connects/disconnects."""
        transport = DummyTransport()
        radio = Kv4pRadio(transport)

        with radio:
            assert radio.is_ready

        assert not radio.is_ready

    def test_frequency_properties(self):
        """Test reading frequency properties after connect."""
        transport = DummyTransport(min_radio_freq=134.0, max_radio_freq=174.0)
        radio = Kv4pRadio(transport)

        radio.connect()
        try:
            assert radio.freq_rx == 134.0
            assert radio.freq_tx == 134.0
        finally:
            radio.disconnect()

    def test_set_frequency(self):
        """Test setting frequency."""
        transport = DummyTransport()
        radio = Kv4pRadio(transport)

        radio.connect()
        try:
            radio.set_frequency(145.500)
            assert radio.freq_rx == 145.500
            assert radio.freq_tx == 145.500
        finally:
            radio.disconnect()

    def test_set_frequency_split(self):
        """Test setting split RX/TX frequencies."""
        transport = DummyTransport()
        radio = Kv4pRadio(transport)

        radio.connect()
        try:
            radio.set_frequency(145.500, 145.600)
            assert radio.freq_rx == 145.500
            assert radio.freq_tx == 145.600
        finally:
            radio.disconnect()

    def test_operation_before_connect_raises(self):
        """Test that operations before connect() raise RadioNotReadyError."""
        transport = DummyTransport()
        radio = Kv4pRadio(transport)

        with pytest.raises(RadioNotReadyError):
            radio.set_frequency(145.500)

    def test_set_bandwidth(self):
        """Test setting bandwidth."""
        transport = DummyTransport()
        radio = Kv4pRadio(transport)

        radio.connect()
        try:
            radio.set_bandwidth("25k")
            assert "25k" in radio.bandwidth or radio.bandwidth == "25k"
        finally:
            radio.disconnect()

    def test_set_squelch(self):
        """Test setting squelch level."""
        transport = DummyTransport()
        radio = Kv4pRadio(transport)

        radio.connect()
        try:
            radio.set_squelch(3)
            assert radio.squelch == 3
        finally:
            radio.disconnect()

    def test_set_high_power(self):
        """Test enabling/disabling high power."""
        transport = DummyTransport()
        radio = Kv4pRadio(transport)

        radio.connect()
        try:
            radio.set_high_power(True)
            assert radio.high_power is True

            radio.set_high_power(False)
            assert radio.high_power is False
        finally:
            radio.disconnect()

    def test_set_tx_allowed(self):
        """Test enabling/disabling TX."""
        transport = DummyTransport()
        radio = Kv4pRadio(transport)

        radio.connect()
        try:
            radio.set_tx_allowed(True)
            assert radio.tx_allowed is True

            radio.set_tx_allowed(False)
            assert radio.tx_allowed is False
        finally:
            radio.disconnect()
