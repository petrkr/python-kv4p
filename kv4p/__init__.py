"""KV4P radio integration."""

from __future__ import annotations

__version__ = "0.0.0"

import logging
from collections.abc import Callable

from kv4p.constants.kiss import KISS_CMD_DATA, KISS_CMD_SETHARDWARE
from kv4p.constants.messages import (
    HOST_STATE_ENABLE_STATUS_REPORTS,
    HOST_STATE_FILTER_HIGH,
    HOST_STATE_FILTER_LOW,
    HOST_STATE_FILTER_PRE,
    HOST_STATE_HIGH_POWER,
    HOST_STATE_RSSI_ENABLED,
    HOST_STATE_RX_AUDIO_OPEN,
    HOST_STATE_TX_ALLOWED,
)
from kv4p.constants.vendor import (
    COMMAND_AUDIO_ADPCM,
    COMMAND_AUDIO_OPUS,
    COMMAND_DEBUG_DEBUG,
    COMMAND_DEBUG_ERROR,
    COMMAND_DEBUG_INFO,
    COMMAND_DEBUG_TRACE,
    COMMAND_DEBUG_WARN,
    COMMAND_DEVICE_STATE,
    COMMAND_HELLO,
    COMMAND_HOST_DESIRED_STATE,
    COMMAND_WINDOW_UPDATE,
    KV4P_PROTOCOL_VERSION,
    KV4P_VENDOR_HEADER_LEN,
    KV4P_VENDOR_PREFIX,
)
from kv4p.flow_control import FlowControlWindow
from kv4p.messages.desired_state import HostDesiredState, bandwidth_to_dra818
from kv4p.messages.device_state import DeviceState
from kv4p.messages.hello import Hello
from kv4p.messages.window_update import WindowUpdate
from kv4p.protocol.kiss import encode_kiss_frame
from kv4p.state_tracker import DeviceStateTracker
from kv4p.transports import Kv4pTransport

logger = logging.getLogger(__name__)


def encode_vendor_payload(command: int, payload: bytes = b"") -> bytes:
    """Build KV4P vendor payload for a KISS SETHARDWARE frame."""
    return KV4P_VENDOR_PREFIX + bytes([KV4P_PROTOCOL_VERSION, command]) + payload


def decode_vendor_payload(payload: bytes) -> tuple[int, bytes] | None:
    """Parse KV4P vendor payload."""
    if len(payload) < KV4P_VENDOR_HEADER_LEN:
        return None
    if payload[:4] != KV4P_VENDOR_PREFIX:
        return None
    if payload[4] != KV4P_PROTOCOL_VERSION:
        return None
    return payload[5], payload[6:]


class RadioNotReadyError(RuntimeError):
    """Raised when an operation requires HELLO to have been received but it hasn't."""


class RadioTransportError(RadioNotReadyError):
    """Raised when an operation is attempted after the transport failed unexpectedly."""


class Kv4pRadio:
    """KV4P-HT radio side of the bridge."""

    def __init__(self, transport: Kv4pTransport) -> None:
        self._transport = transport
        self._flow = FlowControlWindow()
        self._on_rx_audio: Callable[[bytes], None] | None = None
        self._on_sql: Callable[[bool], None] | None = None
        self._on_ax25_frame: Callable[[bytes], None] | None = None
        self._on_device_state: Callable[[DeviceState], None] | None = None
        self._tracker = DeviceStateTracker(
            send_desired_state=self._send_desired_state,
            on_rx_audio=lambda payload: self._on_rx_audio(payload) if self._on_rx_audio else None,
            on_sql=lambda state: self._on_sql(state) if self._on_sql else None,
        )
        self._open = False
        self._transport_error: Exception | None = None

        self._dispatch: dict[int, Callable[[bytes], None]] = {
            COMMAND_DEBUG_INFO: self._handle_debug,
            COMMAND_DEBUG_ERROR: self._handle_debug,
            COMMAND_DEBUG_WARN: self._handle_debug,
            COMMAND_DEBUG_DEBUG: self._handle_debug,
            COMMAND_DEBUG_TRACE: self._handle_debug,
            COMMAND_HELLO: self._handle_hello,
            COMMAND_DEVICE_STATE: self._handle_device_state,
            COMMAND_AUDIO_OPUS: self._handle_rx_audio,
            COMMAND_AUDIO_ADPCM: self._handle_rx_audio,
            COMMAND_WINDOW_UPDATE: self._handle_window_update,
        }

    # -- lifecycle -------------------------------------------------------------

    def __enter__(self) -> Kv4pRadio:
        try:
            self.connect()
        except BaseException:
            self.disconnect()
            raise
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        self.disconnect()

    def connect(self, hello_timeout: float = 5.0) -> None:
        """Open the transport, reset the radio, and wait for HELLO."""
        if self._open:
            return
        self._transport_error = None
        self._transport.open(self._on_kiss_frame, self._on_transport_error)
        self._open = True
        logger.info("radio connect")
        self.reset(hello_timeout=hello_timeout)

    def disconnect(self) -> None:
        """Close radio transport."""
        if not self._open:
            return
        logger.info("radio disconnect")
        try:
            if self.is_ready:
                self.set_ptt(False)
        except Exception:
            logger.exception("failed to clear PTT during disconnect")

        self._transport.close()
        self._open = False
        logger.info("radio disconnected")

    def reset(self, hello_timeout: float = 5.0) -> None:
        """Hardware-reset the radio and wait for it to re-announce itself via HELLO.

        Public so callers can recover a radio that has hung, not just at connect().
        """
        if not self._open:
            raise RuntimeError("radio transport is not connected")
        self._transport.reset()
        if not self._tracker.wait_for_hello(timeout=hello_timeout):
            raise TimeoutError("timed out waiting for HELLO after reset")

    # -- configuration -----------------------------------------------------------
    #
    # All settings below are seeded from the DeviceState carried in HELLO —
    # the firmware always reports its actual tuned state there, right after
    # open()/reset() forces a reboot. Reading a property never involves I/O;
    # each set_*() call sends a full HostDesiredState snapshot (the protocol
    # always wants the complete state, not a delta).

    def set_frequency(self, freq: float, txfreq: float | None = None) -> None:
        """Update the radio's frequency, validated against the range reported in HELLO.

        `freq` sets both RX and TX (simplex). Pass `txfreq` too for
        split/repeater operation, where TX differs from RX.
        """
        self._require_ready()
        version = self._tracker.hello.version
        for value in (freq, txfreq) if txfreq is not None else (freq,):
            if not (version.min_radio_freq <= value <= version.max_radio_freq):
                raise ValueError(
                    f"frequency {value} outside radio range "
                    f"{version.min_radio_freq}-{version.max_radio_freq}"
                )
        self._tracker.set_frequency(rx=freq, tx=txfreq if txfreq is not None else freq)

    def set_bandwidth(self, bandwidth: str) -> None:
        """Update bandwidth ("12.5k" or "25k")."""
        self._require_ready()
        self._tracker.set_bandwidth(bandwidth_to_dra818(bandwidth))

    def set_squelch(self, squelch: int) -> None:
        """Update squelch level."""
        self._require_ready()
        self._tracker.set_squelch(squelch)

    def set_ctcss(self, *, rx: int | None = None, tx: int | None = None) -> None:
        """Update RX/TX CTCSS tone."""
        self._require_ready()
        self._tracker.set_ctcss(rx=rx, tx=tx)

    def set_high_power(self, enabled: bool) -> None:
        """Enable/disable high power output."""
        self._require_ready()
        self._tracker.set_flag(HOST_STATE_HIGH_POWER, enabled)

    def set_tx_allowed(self, enabled: bool) -> None:
        """Enable/disable TX capability."""
        self._require_ready()
        self._tracker.set_flag(HOST_STATE_TX_ALLOWED, enabled)

    def set_rssi(self, enabled: bool) -> None:
        """Enable/disable RSSI reporting."""
        self._require_ready()
        self._tracker.set_flag(HOST_STATE_RSSI_ENABLED, enabled)

    def set_rx_audio_open(self, enabled: bool) -> None:
        """Enable/disable receiving RX audio from the firmware."""
        self._require_ready()
        self._tracker.set_flag(HOST_STATE_RX_AUDIO_OPEN, enabled)

    def set_status_reports(self, enabled: bool) -> None:
        """Enable/disable periodic DEVICE_STATE reports from the firmware."""
        self._require_ready()
        self._tracker.set_flag(HOST_STATE_ENABLE_STATUS_REPORTS, enabled)

    def set_filters(self, *, pre: bool | None = None, high: bool | None = None, low: bool | None = None) -> None:
        """Enable/disable the pre-emphasis/high-pass/low-pass audio filters."""
        self._require_ready()
        for flag, value in (
            (HOST_STATE_FILTER_PRE, pre),
            (HOST_STATE_FILTER_HIGH, high),
            (HOST_STATE_FILTER_LOW, low),
        ):
            if value is not None:
                self._tracker.set_flag(flag, value)

    def set_ptt(self, enabled: bool) -> None:
        """Set PTT requested state."""
        self._require_ready()
        self._tracker.request_ptt(enabled)

    # -- data path ---------------------------------------------------------------

    def send_tx_audio(self, payload: bytes) -> None:
        """Send KV4P-native TX audio payload."""
        self._require_ready()
        self._send_vendor(self._tracker.tx_audio_command, payload, flow_controlled=True)

    def send_ax25_frame(self, payload: bytes) -> None:
        """Send a raw AX.25 frame over the KISS data port."""
        logger.debug("ax25 frame tx bytes=%d", len(payload))
        self._claim_and_write(KISS_CMD_DATA, payload, flow_controlled=True)

    def flush(self) -> None:
        """Flush pending serial writes."""
        self._transport.flush()

    def on_rx_audio(self, callback: Callable[[bytes], None] | None) -> None:
        """Register callback for incoming audio frames."""
        self._on_rx_audio = callback

    def on_sql(self, callback: Callable[[bool], None] | None) -> None:
        """Register callback for squelch open/close events."""
        self._on_sql = callback

    def on_ax25_frame(self, callback: Callable[[bytes], None] | None) -> None:
        """Register callback for incoming AX.25 frames."""
        self._on_ax25_frame = callback

    def on_device_state(self, callback: Callable[[DeviceState], None] | None) -> None:
        """Register callback for device state updates."""
        self._on_device_state = callback

    # -- read-only state -----------------------------------------------------

    @property
    def hello(self) -> Hello | None:
        return self._tracker.hello

    @property
    def is_ready(self) -> bool:
        return self._open and self._transport_error is None and self._tracker.hello is not None

    @property
    def physical_ptt(self) -> bool:
        return self._tracker.physical_ptt

    @property
    def mode(self) -> int | None:
        return self._tracker.mode

    @property
    def codec(self) -> int:
        """Audio codec command in use: COMMAND_AUDIO_OPUS or COMMAND_AUDIO_ADPCM."""
        return self._tracker.tx_audio_command

    @property
    def freq_rx(self) -> float:
        return self._tracker.freq_rx

    @property
    def freq_tx(self) -> float:
        return self._tracker.freq_tx

    @property
    def bandwidth(self) -> str:
        return self._tracker.bandwidth

    @property
    def squelch(self) -> int:
        return self._tracker.squelch

    @property
    def ctcss_rx(self) -> int:
        return self._tracker.ctcss_rx

    @property
    def ctcss_tx(self) -> int:
        return self._tracker.ctcss_tx

    @property
    def high_power(self) -> bool:
        return bool(self._tracker.flags & HOST_STATE_HIGH_POWER)

    @property
    def tx_allowed(self) -> bool:
        return bool(self._tracker.flags & HOST_STATE_TX_ALLOWED)

    @property
    def rssi(self) -> bool:
        return bool(self._tracker.flags & HOST_STATE_RSSI_ENABLED)

    @property
    def rx_audio_open(self) -> bool:
        return bool(self._tracker.flags & HOST_STATE_RX_AUDIO_OPEN)

    @property
    def status_reports(self) -> bool:
        return bool(self._tracker.flags & HOST_STATE_ENABLE_STATUS_REPORTS)

    @property
    def filter_pre(self) -> bool:
        return bool(self._tracker.flags & HOST_STATE_FILTER_PRE)

    @property
    def filter_high(self) -> bool:
        return bool(self._tracker.flags & HOST_STATE_FILTER_HIGH)

    @property
    def filter_low(self) -> bool:
        return bool(self._tracker.flags & HOST_STATE_FILTER_LOW)

    # -- incoming frame routing -----------------------------------------------

    def _on_kiss_frame(self, kiss_command: int, payload: bytes) -> None:
        port_command = kiss_command & 0x0F
        if port_command == KISS_CMD_DATA:
            self._handle_ax25_frame(payload)
            return

        if port_command != KISS_CMD_SETHARDWARE:
            logger.debug("ignore KISS command=0x%02x bytes=%d", kiss_command, len(payload))
            return

        decoded = decode_vendor_payload(payload)
        if decoded is None:
            logger.warning("ignore non-KV4P vendor frame bytes=%d", len(payload))
            return

        command, body = decoded
        handler = self._dispatch.get(command)
        if handler is None:
            logger.debug("ignore KV4P command=0x%02x bytes=%d", command, len(body))
            return
        try:
            handler(body)
        except Exception:
            logger.exception("failed to handle KV4P command=0x%02x bytes=%d", command, len(body))

    def _handle_ax25_frame(self, payload: bytes) -> None:
        logger.debug("ax25 frame rx bytes=%d", len(payload))
        if self._on_ax25_frame is not None:
            self._on_ax25_frame(payload)

    def _handle_debug(self, payload: bytes) -> None:
        text = payload.decode("utf-8", errors="replace").strip()
        if text:
            logger.info("firmware: %s", text)

    def _handle_hello(self, payload: bytes) -> None:
        hello = Hello.from_bytes(payload)
        self._flow.reset(hello.version.window_size)
        self._tracker.on_hello(hello)

    def _handle_device_state(self, payload: bytes) -> None:
        state = DeviceState.from_bytes(payload)
        self._tracker.on_device_state(state)
        if self._on_device_state is not None:
            self._on_device_state(state)

    def _handle_rx_audio(self, payload: bytes) -> None:
        self._tracker.on_rx_audio(payload)

    def _handle_window_update(self, payload: bytes) -> None:
        size = WindowUpdate.from_bytes(payload).size
        self._flow.add(size)
        logger.debug("window update size=%d", size)

    def _on_transport_error(self, exc: Exception) -> None:
        """Called from the transport's background thread when it dies unexpectedly."""
        logger.error("transport error: %s", exc)
        self._transport_error = exc

    # -- outgoing frames -------------------------------------------------------

    def _send_desired_state(self, state: HostDesiredState) -> None:
        self._send_vendor(COMMAND_HOST_DESIRED_STATE, state.to_bytes(), flow_controlled=False)

    def _send_vendor(self, command: int, payload: bytes = b"", *, flow_controlled: bool) -> None:
        self._claim_and_write(KISS_CMD_SETHARDWARE, encode_vendor_payload(command, payload), flow_controlled=flow_controlled)

    def _claim_and_write(self, kiss_command: int, payload: bytes, *, flow_controlled: bool) -> None:
        if flow_controlled:
            frame_size = len(encode_kiss_frame(kiss_command, payload))
            if not self._flow.claim(frame_size):
                logger.warning("drop KISS command=0x%02x frame; flow-control window exhausted", kiss_command)
                return
        self._transport.write_frame(kiss_command, payload)

    def _require_ready(self) -> None:
        if self._transport_error is not None:
            raise RadioTransportError(f"transport failed: {self._transport_error}") from self._transport_error
        if not self.is_ready:
            raise RadioNotReadyError("radio has not completed the HELLO handshake yet")
