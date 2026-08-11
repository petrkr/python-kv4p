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

    def test_hello_filters_device_state_squelched_bit(self):
        """Test that HELLO initialization filters out DEVICE_STATE_SQUELCHED from flags.

        This test verifies that when firmware reports DEVICE_STATE_SQUELCHED bit in HELLO,
        it is NOT copied into the tracker's internal HOST_STATE flags. The bit represents
        runtime state (whether SQL is currently squelched), not a persisted host setting.
        """
        from kv4p.constants.messages import DEVICE_STATE_SQUELCHED, HOST_STATE_RADIO_CONFIG_VALID

        # Create DummyTransport that reports DEVICE_STATE_SQUELCHED in HELLO
        transport = DummyTransport(device_state_flags=DEVICE_STATE_SQUELCHED | HOST_STATE_RADIO_CONFIG_VALID)
        radio = Kv4pRadio(transport)

        radio.connect()
        try:
            # Tracker flags should have RADIO_CONFIG_VALID but NOT SQUELCHED
            tracker_flags = radio._tracker.flags
            assert tracker_flags & HOST_STATE_RADIO_CONFIG_VALID, "Should have RADIO_CONFIG_VALID"
            assert not (tracker_flags & DEVICE_STATE_SQUELCHED), "Should NOT have DEVICE_STATE_SQUELCHED"
        finally:
            radio.disconnect()

    def test_sql_callback_fires_on_state_change(self):
        """Test that SQL callback fires when SQL state changes."""
        transport = DummyTransport()
        radio = Kv4pRadio(transport)
        sql_events = []

        def on_sql(open_state):
            sql_events.append(open_state)

        radio.on_sql(on_sql)

        radio.connect()
        try:
            # Initial state: SQL closed
            assert len(sql_events) >= 1
            # DummyTransport simulates SQL opening after a delay
            import time
            time.sleep(1)
            # Should have captured SQL open event
            assert True in sql_events, f"Expected SQL open event, got {sql_events}"
        finally:
            radio.disconnect()
