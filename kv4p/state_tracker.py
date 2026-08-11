"""Protocol state machine: HELLO handshake, device-state cache, HostDesiredState building."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from kv4p.constants.messages import (
    DEVICE_STATE_PHYS_PTT_DOWN,
    DEVICE_STATE_SQUELCHED,
    DEVICE_STATE_TX_ACTIVE,
    HOST_STATE_PTT_REQUESTED,
    HOST_STATE_RADIO_CONFIG_VALID,
    HOST_STATE_TX_ALLOWED,
)
from kv4p.constants.vendor import COMMAND_AUDIO_ADPCM, COMMAND_AUDIO_OPUS
from kv4p.messages.desired_state import HostDesiredState, dra818_to_bandwidth
from kv4p.messages.device_state import DeviceState, RadioMode
from kv4p.messages.hello import Hello

logger = logging.getLogger(__name__)

# Firmware 17 is the last known version using Opus TX audio on 0x07. There is
# no published feature bit to detect ADPCM (0x0C) support, and it's unknown
# at which version upstream actually switches — this threshold is a guess
# based on "17 is confirmed 0x07" and must be revisited once a newer firmware
# version's actual behavior is known.
_OPUS_MAX_FW = 17


class DeviceStateTracker:
    """Tracks the firmware handshake/state and builds outgoing HostDesiredState frames.

    Radio settings (frequency, bandwidth, squelch, CTCSS, ...) are seeded from
    the DeviceState carried in HELLO — the firmware always reports its actual
    tuned state there, right after `Kv4pRadio.open()`/`reset()` forces a
    reboot. There is no separate "desired settings" object with its own
    defaults; `set_*()` calls mutate this tracked state directly.
    """

    def __init__(
        self,
        send_desired_state: Callable[[HostDesiredState], None],
        on_rx_audio: Callable[[bytes], None] | None = None,
        on_sql: Callable[[bool], None] | None = None,
        on_phy_ptt: Callable[[bool], None] | None = None,
        on_tx_active: Callable[[bool], None] | None = None,
    ) -> None:
        self._send_desired_state = send_desired_state
        self._on_rx_audio = on_rx_audio
        self._on_sql = on_sql
        self._on_phy_ptt = on_phy_ptt
        self._on_tx_active = on_tx_active

        self._lock = threading.RLock()
        self._hello_event = threading.Event()
        self._hello: Hello | None = None
        self._device_state: DeviceState | None = None
        self._sequence = 0
        self._flags = HOST_STATE_RADIO_CONFIG_VALID
        self._tx_audio_command = COMMAND_AUDIO_OPUS

        # Radio settings, seeded from HELLO's DeviceState in on_hello().
        self._freq_rx = 0.0
        self._freq_tx = 0.0
        self._bw = 0
        self._squelch = 0
        self._ctcss_rx = 0
        self._ctcss_tx = 0

        self._last_sql_open: bool | None = None
        self._last_phy_ptt: bool | None = None
        self._last_tx_active: bool | None = None
        self._last_status_key: tuple[object, ...] | None = None

    # -- handshake / incoming state -----------------------------------------

    def on_hello(self, hello: Hello) -> None:
        """Handle a HELLO frame (only ever sent once, right after the ESP32 boots)."""
        with self._lock:
            self._hello = hello
            self._device_state = hello.device_state
            self._sequence = hello.device_state.applied_sequence
            self._flags = (hello.device_state.flags
                           & ~(DEVICE_STATE_PHYS_PTT_DOWN | DEVICE_STATE_TX_ACTIVE | DEVICE_STATE_SQUELCHED )) \
                            | HOST_STATE_RADIO_CONFIG_VALID
            self._seed_settings_locked(hello.device_state)
            self._tx_audio_command = (
                COMMAND_AUDIO_ADPCM if hello.version.ver > _OPUS_MAX_FW else COMMAND_AUDIO_OPUS
            )
        logger.info(
            "HELLO firmware=%d window=%d radio=%s range=%.3f-%.3f features=0x%02x",
            hello.version.ver,
            hello.version.window_size,
            hello.version.radio_module_status,
            hello.version.min_radio_freq,
            hello.version.max_radio_freq,
            hello.version.features,
        )
        self._hello_event.set()
        self.on_device_state(hello.device_state)

    def wait_for_hello(self, timeout: float | None = None) -> bool:
        """Block until HELLO has been received."""
        return self._hello_event.wait(timeout=timeout)

    def on_device_state(self, state: DeviceState) -> None:
        """Handle a DEVICE_STATE frame."""
        with self._lock:
            self._device_state = state
            sql_open = state.sql_open
            if state.applied_sequence > self._sequence:
                self._sequence = state.applied_sequence

        self._log_device_status(state)

        if sql_open != self._last_sql_open:
            self._last_sql_open = sql_open
            logger.info("sql %s", "open" if sql_open else "closed")
            if self._on_sql is not None:
                self._on_sql(sql_open)

        phy_ptt = bool(state.flags & DEVICE_STATE_PHYS_PTT_DOWN)
        if phy_ptt != self._last_phy_ptt:
            self._last_phy_ptt = phy_ptt
            logger.info("physical ptt %s", "down" if phy_ptt else "up")
            if self._on_phy_ptt is not None:
                self._on_phy_ptt(phy_ptt)

        tx_active = bool(state.flags & DEVICE_STATE_TX_ACTIVE)
        if tx_active != self._last_tx_active:
            self._last_tx_active = tx_active
            logger.info("tx active %s", tx_active)
            if self._on_tx_active is not None:
                self._on_tx_active(tx_active)

    def on_rx_audio(self, payload: bytes) -> None:
        """Handle an RX audio payload."""
        if self._on_rx_audio is not None:
            self._on_rx_audio(payload)

    # -- setters ----------------------------------------------------------------

    def request_ptt(self, enabled: bool) -> bool:
        """Set/clear the PTT-requested bit. Returns True if the flags actually changed."""
        with self._lock:
            if enabled and not (self._flags & HOST_STATE_TX_ALLOWED):
                logger.warning("PTT requested while TX is not allowed")
            old_flags = self._flags
            if enabled:
                self._flags |= HOST_STATE_PTT_REQUESTED
            else:
                self._flags &= ~HOST_STATE_PTT_REQUESTED
            if self._flags == old_flags:
                return False
            logger.info("ptt %s", "on" if enabled else "off")
            self._send_desired_state_locked()
            return True

    def set_frequency(self, *, rx: float | None = None, tx: float | None = None) -> None:
        """Update RX/TX frequency and send the new desired state."""
        with self._lock:
            if rx is not None:
                self._freq_rx = rx
            if tx is not None:
                self._freq_tx = tx
            self._send_desired_state_locked()

    def set_bandwidth(self, bw: int) -> None:
        """Update bandwidth (a DRA818_* constant) and send the new desired state."""
        with self._lock:
            self._bw = bw
            self._send_desired_state_locked()

    def set_squelch(self, squelch: int) -> None:
        """Update squelch level and send the new desired state."""
        with self._lock:
            self._squelch = squelch
            self._send_desired_state_locked()

    def set_ctcss(self, *, rx: int | None = None, tx: int | None = None) -> None:
        """Update RX/TX CTCSS tone and send the new desired state."""
        with self._lock:
            if rx is not None:
                self._ctcss_rx = rx
            if tx is not None:
                self._ctcss_tx = tx
            self._send_desired_state_locked()

    def set_flag(self, flag: int, enabled: bool) -> None:
        """Set/clear one of the HOST_STATE_* option bits and send the new desired state."""
        with self._lock:
            if enabled:
                self._flags |= flag
            else:
                self._flags &= ~flag
            self._send_desired_state_locked()

    def _send_desired_state_locked(self) -> None:
        applied_sequence = self._device_state.applied_sequence if self._device_state is not None else 0
        self._sequence = max(self._sequence, applied_sequence) + 1
        state = self._build_desired_state_locked()
        # Release the lock before handing off to I/O: the caller's send callback
        # may block on flow control / serial writes and must not hold up readers
        # of phy_ptt/mode from other threads.
        self._lock.release()
        try:
            self._send_desired_state(state)
        finally:
            self._lock.acquire()
        logger.info(
            (
                "desired state sequence=%d flags=0x%04x rx=%.5f tx=%.5f "
                "bw=%s squelch=%d ctcss_rx=%d ctcss_tx=%d"
            ),
            state.sequence,
            state.flags,
            state.freq_rx,
            state.freq_tx,
            dra818_to_bandwidth(state.bw),
            state.squelch,
            state.ctcss_rx,
            state.ctcss_tx,
        )

    def _build_desired_state_locked(self) -> HostDesiredState:
        return HostDesiredState(
            sequence=self._sequence,
            memory_id=-1,
            flags=self._flags,
            bw=self._bw,
            freq_tx=self._freq_tx,
            freq_rx=self._freq_rx,
            ctcss_tx=self._ctcss_tx,
            squelch=self._squelch,
            ctcss_rx=self._ctcss_rx,
        )

    # -- derived properties -----------------------------------------------

    @property
    def hello(self) -> Hello | None:
        with self._lock:
            return self._hello

    @property
    def device_state(self) -> DeviceState | None:
        with self._lock:
            return self._device_state

    @property
    def flags(self) -> int:
        with self._lock:
            return self._flags

    @property
    def freq_rx(self) -> float:
        with self._lock:
            return self._freq_rx

    @property
    def freq_tx(self) -> float:
        with self._lock:
            return self._freq_tx

    @property
    def bandwidth(self) -> str:
        with self._lock:
            return dra818_to_bandwidth(self._bw)

    @property
    def squelch(self) -> int:
        with self._lock:
            return self._squelch

    @property
    def ctcss_rx(self) -> int:
        with self._lock:
            return self._ctcss_rx

    @property
    def ctcss_tx(self) -> int:
        with self._lock:
            return self._ctcss_tx

    @property
    def tx_audio_command(self) -> int:
        """TX audio vendor command, guessed once in on_hello() from the firmware version.

        See `_OPUS_MAX_FW` above — there is no feature bit to detect this properly yet.
        """
        with self._lock:
            return self._tx_audio_command

    @property
    def phy_ptt(self) -> bool:
        with self._lock:
            if self._device_state is None:
                return False
            return bool(self._device_state.flags & DEVICE_STATE_PHYS_PTT_DOWN)

    @property
    def tx_active(self) -> bool:
        with self._lock:
            if self._device_state is None:
                return False
            return bool(self._device_state.flags & DEVICE_STATE_TX_ACTIVE)

    @property
    def sql_open(self) -> bool:
        with self._lock:
            if self._device_state is None:
                return False
            return self._device_state.sql_open

    @property
    def mode(self) -> RadioMode | None:
        with self._lock:
            if self._device_state is None:
                return None
            return self._device_state.mode

    # -- internals -----------------------------------------------------------

    def _seed_settings_locked(self, state: DeviceState) -> None:
        """Seed radio settings from the firmware's actual tuned state at boot."""
        self._freq_rx = state.freq_rx
        self._freq_tx = state.freq_tx
        self._bw = state.bw
        self._squelch = state.squelch
        self._ctcss_rx = state.ctcss_rx
        self._ctcss_tx = state.ctcss_tx

    def _log_device_status(self, state: DeviceState) -> None:
        key = (
            state.applied_sequence,
            state.flags,
            state.mode,
            state.last_error,
            round(state.freq_rx, 5),
            round(state.freq_tx, 5),
            state.bw,
            state.squelch,
            state.ctcss_rx,
            state.ctcss_tx,
            state.radio_module_status,
            state.latest_rssi if state.mode == RadioMode.TX else None,
        )
        if key == self._last_status_key:
            return
        self._last_status_key = key
        logger.info(
            (
                "radio status mode=%s sql=%s rx=%.5f tx=%.5f bw=%s "
                "squelch=%d ctcss_rx=%d ctcss_tx=%d flags=0x%04x "
                "applied_sequence=%d error=%d rssi=%d module=%s"
            ),
            state.mode.name,
            "open" if state.sql_open else "closed",
            state.freq_rx,
            state.freq_tx,
            dra818_to_bandwidth(state.bw),
            state.squelch,
            state.ctcss_rx,
            state.ctcss_tx,
            state.flags,
            state.applied_sequence,
            state.last_error,
            state.latest_rssi,
            state.radio_module_status,
        )
