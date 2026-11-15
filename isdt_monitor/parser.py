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
    voltage_mv: int
    current_ma_unverified: int
    resistance_mohm_unverified: int
    temperature_tenths_c_unverified: int
    unknown_a: int
    unknown_b: int
    unknown_c: int

    @property
    def temperature_c_unverified(self) -> float:
        return self.temperature_tenths_c_unverified / 10.0

    @property
    def has_nonzero_measurement(self) -> bool:
        return any(
            (
                self.voltage_mv,
                self.current_ma_unverified,
                self.resistance_mohm_unverified,
                self.temperature_tenths_c_unverified,
                self.unknown_a,
                self.unknown_b,
                self.unknown_c,
            )
        )

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["temperature_c_unverified"] = self.temperature_c_unverified
        result["has_nonzero_measurement"] = self.has_nonzero_measurement
        return result


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
        frame = bytes.fromhex(compact)
    except ValueError as exc:
        raise FrameError("Reading-Hex enthält ungültige Zeichen.") from exc
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
        raw_frame=frame.hex(),
        frame_channel=frame[6],
        voltage_mv=u16(13),
        current_ma_unverified=u16(15),
        resistance_mohm_unverified=u16(17),
        temperature_tenths_c_unverified=u16(19),
        unknown_a=u16(21),
        unknown_b=u32(23),
        unknown_c=u32(27),
    )


def parse_isdttool_output(output: str) -> ExperimentalMetrics:
    return parse_reading_hex(extract_reading_hex(output))
