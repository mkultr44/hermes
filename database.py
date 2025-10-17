import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS packages (
    sendungsnr TEXT PRIMARY KEY,
    zone TEXT NOT NULL,
    received_at TEXT NOT NULL,
    name TEXT
);

CREATE TABLE IF NOT EXISTS directory (
    sendungsnr TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class Database:
    """Lightweight wrapper for the SQLite database used by the app."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._initialise()

    def _initialise(self) -> None:
        with self._conn:
            self._conn.executescript(_DB_SCHEMA)

    @contextmanager
    def cursor(self) -> Iterable[sqlite3.Cursor]:
        with self._lock:
            cur = self._conn.cursor()
            try:
                yield cur
            finally:
                cur.close()

    def upsert_package(self, sendungsnr: str, zone: str, received_at: str, name: Optional[str]) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO packages (sendungsnr, zone, received_at, name)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(sendungsnr) DO UPDATE SET
                    zone=excluded.zone,
                    received_at=excluded.received_at,
                    name=excluded.name
                """,
                (sendungsnr, zone, received_at, name),
            )
            self._conn.commit()

    def get_all_packages(self) -> List[sqlite3.Row]:
        with self.cursor() as cur:
            cur.execute(
                "SELECT sendungsnr, name, zone, received_at FROM packages ORDER BY datetime(received_at) DESC"
            )
            return cur.fetchall()

    def replace_directory(self, entries: Sequence[Tuple[str, str, str]]) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM directory")
            self._conn.executemany(
                "INSERT INTO directory (sendungsnr, name, updated_at) VALUES (?, ?, ?)", entries
            )
            self._conn.commit()

    def get_directory_entries(self) -> List[sqlite3.Row]:
        with self.cursor() as cur:
            cur.execute("SELECT sendungsnr, name FROM directory")
            return cur.fetchall()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
