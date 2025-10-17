import csv
import io
import threading
from datetime import datetime, timezone
from typing import Callable, Optional

import requests

from database import Database

SYNC_INTERVAL_SECONDS = 30


class DirectorySyncThread(threading.Thread):
    """Background worker that keeps the directory table in sync with the CSV source."""

    def __init__(
        self,
        database: Database,
        url: str,
        on_error: Optional[Callable[[str], None]] = None,
        *,
        interval: int = SYNC_INTERVAL_SECONDS,
    ) -> None:
        super().__init__(daemon=True)
        self._db = database
        self._url = url
        self._interval = interval
        self._stop = threading.Event()
        self._on_error = on_error

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                self._sync_once()
            except Exception as exc:  # noqa: BLE001 - surface the error text via the callback
                if self._on_error:
                    self._on_error(str(exc))
            finally:
                self._stop.wait(self._interval)

    def stop(self) -> None:
        self._stop.set()

    def _sync_once(self) -> None:
        response = requests.get(self._url, timeout=15)
        response.raise_for_status()
        csv_bytes = response.content
        text_stream = io.StringIO(csv_bytes.decode("utf-8"))
        reader = csv.DictReader(text_stream)

        now = datetime.now(timezone.utc).isoformat()
        entries = []
        for row in reader:
            sendungsnr = row.get("sendungsnr") or row.get("Sendungsnr")
            name = row.get("name") or row.get("Name")
            if not sendungsnr or not name:
                continue
            entries.append((sendungsnr.strip(), name.strip(), now))

        if entries:
            self._db.replace_directory(entries)
