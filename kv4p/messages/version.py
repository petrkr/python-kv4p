"""Firmware version payload (part of HELLO)."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntFlag

_VERSION = struct.Struct("<HcIBffB")


class RadioFeatures(IntFlag):
    """Firmware capability flags, as reported in ``Version.features``."""

    HAS_HL = 1 << 0
    HAS_PHY_PTT = 1 << 1
    HAS_ESP32_AFSK = 1 << 2

    @property
    def hl(self) -> bool:
        """True when the firmware reports HL support."""
        return RadioFeatures.HAS_HL in self

    @property
    def phy_ptt(self) -> bool:
        """True when the firmware reports a physical PTT input."""
        return RadioFeatures.HAS_PHY_PTT in self

    @property
    def esp32_afsk(self) -> bool:
        """True when the firmware reports ESP32-side AFSK support."""
        return RadioFeatures.HAS_ESP32_AFSK in self


@dataclass(frozen=True, slots=True)
class Version:
    """Firmware version payload."""

    ver: int
    radio_module_status: str
    window_size: int
    rf_module_type: int
    min_radio_freq: float
    max_radio_freq: float
    features: RadioFeatures

    @classmethod
    def from_bytes(cls, payload: bytes) -> Version:
        """Parse Version."""
        if len(payload) != _VERSION.size:
            raise ValueError(f"Version payload must be {_VERSION.size} bytes, got {len(payload)}")
        values = _VERSION.unpack(payload)
        return cls(
            ver=values[0],
            radio_module_status=values[1].decode("ascii", errors="replace"),
            window_size=values[2],
            rf_module_type=values[3],
            min_radio_freq=values[4],
            max_radio_freq=values[5],
            features=RadioFeatures(values[6]),
        )
