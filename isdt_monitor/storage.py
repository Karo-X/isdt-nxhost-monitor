"""SQLite history storage using only the Python standard library."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
import sqlite3
from typing import Any


COLUMNS = (
    "observed_at",
    "epoch",
    "channel",
    "frame_channel",
    "code_7_candidate",
    "code_8_candidate",
    "code_9_candidate",
    "temperature_c_candidate",
    "code_11_candidate",
    "state_or_soc_candidate",
    "voltage_mv",
    "current_ma_unverified",
    "resistance_mohm_unverified",
    "unknown_offset19_u16",
    "capacity_mah_candidate",
    "elapsed_seconds_candidate",
    "temperature_tenths_c_unverified",
    "unknown_a",
    "unknown_b",
    "unknown_c",
    "raw_frame",
    "raw_output",
    "error",
)


class HistoryStore:
    def __init__(self, path: Path, max_history_per_slot: int = 5000):
        self.path = path
        self.max_history_per_slot = max(10, int(max_history_per_slot))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    observed_at TEXT NOT NULL,
                    epoch REAL NOT NULL,
                    channel INTEGER NOT NULL,
                    frame_channel INTEGER,
                    code_7_candidate INTEGER,
                    code_8_candidate INTEGER,
                    code_9_candidate INTEGER,
                    temperature_c_candidate INTEGER,
                    code_11_candidate INTEGER,
                    state_or_soc_candidate INTEGER,
                    voltage_mv INTEGER,
                    current_ma_unverified INTEGER,
                    resistance_mohm_unverified INTEGER,
                    unknown_offset19_u16 INTEGER,
                    capacity_mah_candidate INTEGER,
                    elapsed_seconds_candidate INTEGER,
                    temperature_tenths_c_unverified INTEGER,
                    unknown_a INTEGER,
                    unknown_b INTEGER,
                    unknown_c INTEGER,
                    raw_frame TEXT,
                    raw_output TEXT NOT NULL,
                    error TEXT
                )
                """
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_samples_channel_id "
                "ON samples(channel, id DESC)"
            )
            existing = {row[1] for row in db.execute("PRAGMA table_info(samples)")}
            for name in (
                "temperature_c_candidate",
                "state_or_soc_candidate",
                "code_7_candidate",
                "code_8_candidate",
                "code_9_candidate",
                "code_11_candidate",
                "unknown_offset19_u16",
                "capacity_mah_candidate",
                "elapsed_seconds_candidate",
            ):
                if name not in existing:
                    db.execute(f"ALTER TABLE samples ADD COLUMN {name} INTEGER")

    def add(self, sample: dict[str, Any]) -> None:
        placeholders = ",".join("?" for _ in COLUMNS)
        with self._connect() as db:
            db.execute(
                f"INSERT INTO samples ({','.join(COLUMNS)}) VALUES ({placeholders})",
                [sample.get(column) for column in COLUMNS],
            )
            db.execute(
                """
                DELETE FROM samples
                WHERE channel = ? AND id NOT IN (
                    SELECT id FROM samples WHERE channel = ?
                    ORDER BY id DESC LIMIT ?
                )
                """,
                (sample["channel"], sample["channel"], self.max_history_per_slot),
            )

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        # Backfill new interpretations when reading rows created by v0.1.
        if result.get("unknown_offset19_u16") is None:
            result["unknown_offset19_u16"] = result.get("temperature_tenths_c_unverified")
        if result.get("capacity_mah_candidate") is None:
            result["capacity_mah_candidate"] = result.get("unknown_b")
        if result.get("elapsed_seconds_candidate") is None:
            result["elapsed_seconds_candidate"] = result.get("unknown_c")
        if result.get("temperature_c_candidate") is None and result.get("raw_frame"):
            try:
                from .parser import parse_reading_hex

                parsed = parse_reading_hex(result["raw_frame"])
                result["temperature_c_candidate"] = parsed.temperature_c_candidate
                result["state_or_soc_candidate"] = parsed.state_or_soc_candidate
                result["code_7_candidate"] = parsed.code_7_candidate
                result["code_8_candidate"] = parsed.code_8_candidate
                result["code_9_candidate"] = parsed.code_9_candidate
                result["code_11_candidate"] = parsed.code_11_candidate
            except (TypeError, ValueError):
                pass
        result["temperature_c_unverified"] = result.get("temperature_c_candidate")
        result["has_nonzero_measurement"] = any(
            result.get(key)
            for key in (
                "voltage_mv",
                "current_ma_unverified",
                "resistance_mohm_unverified",
                "capacity_mah_candidate",
            )
        )
        return result

    def latest(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT * FROM samples WHERE id IN (
                    SELECT MAX(id) FROM samples GROUP BY channel
                ) ORDER BY channel
                """
            ).fetchall()
        return [self._row(row) for row in rows]

    def recent(self, limit: int = 80) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM samples ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row(row) for row in rows]

    def history(self, channel: int, limit: int = 500) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), self.max_history_per_slot))
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM samples WHERE channel = ? ORDER BY id DESC LIMIT ?",
                (channel, limit),
            ).fetchall()
        return [self._row(row) for row in reversed(rows)]

    def csv_text(self) -> str:
        output = StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(COLUMNS)
        with self._connect() as db:
            rows = db.execute(
                f"SELECT {','.join(COLUMNS)} FROM samples ORDER BY id"
            )
            writer.writerows(rows)
        return output.getvalue()
