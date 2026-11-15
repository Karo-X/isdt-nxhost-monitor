"""Experimental parser for NXHOST debug frames emitted by isdttool."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re


READING_RE = re.compile(r"^\s*Reading\s+([0-9a-fA-F\s]+?)\s*$", re.MULTILINE)
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
MINIMUM_FRAME_BYTES = 31


class FrameError(ValueError):
    """Raised when no usable NXHOST debug frame can be decoded."""


@dataclass(frozen=True)
class ExperimentalMetrics:
    raw_frame: str
    frame_channel: int
    code_7_candidate: int
    code_8_candidate: int
    code_9_candidate: int
    temperature_c_candidate: int
    code_11_candidate: int
    state_or_soc_candidate: int
    voltage_mv: int
    current_ma_unverified: int
    resistance_mohm_unverified: int
    unknown_offset19_u16: int
    unknown_a: int
    capacity_mah_candidate: int
    elapsed_seconds_candidate: int

    @property
    def battery_present_candidate(self) -> bool:
        """Observed slot-presence marker: 1 with a cell, 4 when empty."""
        return self.code_9_candidate == 1

    @property
    def has_nonzero_measurement(self) -> bool:
        # Compatibility name used by the current web API.
        return self.battery_present_candidate

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        # Compatibility aliases keep existing databases and CSV consumers usable.
        result["temperature_c_unverified"] = self.temperature_c_candidate
        result["temperature_tenths_c_unverified"] = None
        result["unknown_b"] = self.capacity_mah_candidate
        result["unknown_c"] = self.elapsed_seconds_candidate
        result["battery_present_candidate"] = self.battery_present_candidate
        result["has_nonzero_measurement"] = self.has_nonzero_measurement
        return result


def _destuff_frame(frame: bytes) -> bytes:
    """Collapse duplicated 0xAA bytes after the three-byte frame header.

    NXHOST byte-stuffs a payload byte of 0xAA as ``AA AA``. The header's sync
    byte at index 2 is not stuffed. A live 1450 mV sample (0x05AA) exposed this
    behavior by producing a 65-byte debug frame.
    """
    if len(frame) <= 3:
        return frame
    decoded = bytearray(frame[:3])
    index = 3
    while index < len(frame):
        value = frame[index]
        decoded.append(value)
        if value == 0xAA and index + 1 < len(frame) and frame[index + 1] == 0xAA:
            index += 2
        else:
            index += 1
    return bytes(decoded)


def extract_reading_hex(output: str) -> str:
    """Return the final ``Reading ...`` frame from isdttool debug output."""
    clean_output = ANSI_RE.sub("", output)
    matches = READING_RE.findall(clean_output)
    if not matches:
        raise FrameError("Keine 'Reading'-Hexzeile in der isdttool-Ausgabe gefunden.")
    return re.sub(r"\s+", "", matches[-1]).lower()


def parse_reading_hex(raw_hex: str) -> ExperimentalMetrics:
    """Decode the experimentally identified little-endian fields.

    Byte offsets are zero-based.  Field meanings are not protocol-verified.
    """
    compact = re.sub(r"\s+", "", raw_hex)
    if not compact or len(compact) % 2:
        raise FrameError("Reading-Hex ist leer oder hat eine ungerade Länge.")
    try:
        raw_frame = bytes.fromhex(compact)
    except ValueError as exc:
        raise FrameError("Reading-Hex enthält ungültige Zeichen.") from exc
    frame = _destuff_frame(raw_frame)
    if len(frame) < MINIMUM_FRAME_BYTES:
        raise FrameError(
            f"Reading-Frame ist zu kurz: {len(frame)} statt mindestens "
            f"{MINIMUM_FRAME_BYTES} Bytes."
        )

    def u16(offset: int) -> int:
        return int.from_bytes(frame[offset : offset + 2], "little", signed=False)

    def u32(offset: int) -> int:
        return int.from_bytes(frame[offset : offset + 4], "little", signed=False)

    return ExperimentalMetrics(
        raw_frame=raw_frame.hex(),
        frame_channel=frame[6],
        code_7_candidate=frame[7],
        code_8_candidate=frame[8],
        code_9_candidate=frame[9],
        temperature_c_candidate=frame[10],
        code_11_candidate=frame[11],
        state_or_soc_candidate=frame[12],
        voltage_mv=u16(13),
        current_ma_unverified=u16(15),
        resistance_mohm_unverified=u16(17),
        unknown_offset19_u16=u16(19),
        unknown_a=u16(21),
        capacity_mah_candidate=u32(23),
        elapsed_seconds_candidate=u32(27),
    )


def parse_isdttool_output(output: str) -> ExperimentalMetrics:
    return parse_reading_hex(extract_reading_hex(output))
