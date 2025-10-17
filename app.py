from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

import ttkbootstrap as ttk
from rapidfuzz import fuzz, process
from ttkbootstrap.constants import CENTER, LEFT, RIGHT, TOP, X

from database import Database
from sync import DirectorySyncThread

CSV_URL = "https://nextcloud.aralbruehl.de/public.php/dav/files/mJAaPjgBycC7d7y/hermes_final.csv"
APP_WIDTH = 1280
APP_HEIGHT = 800
PRIMARY_BLUE = "#0078D7"
ALERT_RED = "#D00000"
WHITE = "#FFFFFF"


class HermesApp:
    def __init__(self) -> None:
        self._db = Database(Path("paket.db"))
        self._window = ttk.Window(themename="flatly")
        self._window.title("Hermes Paket-Zonen-Manager")
        self._window.geometry(f"{APP_WIDTH}x{APP_HEIGHT}")
        self._window.resizable(False, False)

        self._active_zone: Optional[str] = None
        self._scan_counter = 0
        self._blink_state = True
        self._search_update_job: Optional[str] = None

        self._build_style()
        self._build_ui()

        self._sync_thread = DirectorySyncThread(self._db, CSV_URL, on_error=self._show_sync_error)
        self._sync_thread.start()

        self._window.protocol("WM_DELETE_WINDOW", self._on_close)
        self._window.after(500, self._ensure_focus)
        self._window.after(0, self._update_blink)
        self._window.after(0, self._refresh_packages)

    def _build_style(self) -> None:
        style = self._window.style
        style.configure("Counter.TLabel", font=("Helvetica", 20, "bold"), foreground="black")
        style.configure("CounterValue.TLabel", font=("Helvetica", 28, "bold"), foreground=ALERT_RED)
        style.configure("Zone.TButton", font=("Helvetica", 16, "bold"), padding=15)
        style.configure("WideZone.TButton", font=("Helvetica", 16, "bold"), padding=(15, 22))
        style.map(
            "Zone.TButton",
            background=[("active", PRIMARY_BLUE)],
            foreground=[("active", WHITE)],
        )
        style.map(
            "WideZone.TButton",
            background=[("active", PRIMARY_BLUE)],
            foreground=[("active", WHITE)],
        )

    def _build_ui(self) -> None:
        main = ttk.Frame(self._window, padding=20)
        main.pack(fill=X, expand=True)

        top_frame = ttk.Frame(main)
        top_frame.pack(fill=X, pady=(0, 10))

        search_frame = ttk.Labelframe(top_frame, text="Fuzzy-Suche", padding=10)
        search_frame.pack(side=LEFT, fill=X, expand=True)

        self._search_var = ttk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self._search_var, font=("Helvetica", 16))
        search_entry.pack(fill=X)
        search_entry.bind("<KeyRelease>", self._schedule_search_update)

        self._results = ttk.Treeview(
            search_frame,
            columns=("sendungsnr", "name", "zone", "received_at"),
            show="headings",
            height=10,
        )
        self._results.heading("sendungsnr", text="Sendungsnummer")
        self._results.heading("name", text="Name")
        self._results.heading("zone", text="Zone")
        self._results.heading("received_at", text="Eingang")
        self._results.column("sendungsnr", width=200)
        self._results.column("name", width=280)
        self._results.column("zone", width=120, anchor=CENTER)
        self._results.column("received_at", width=200)
        self._results.pack(fill=X, pady=(10, 0))

        status_frame = ttk.Frame(top_frame)
        status_frame.pack(side=RIGHT, padx=(20, 0))

        counter_label = ttk.Label(status_frame, text="Eingebucht:", style="Counter.TLabel")
        counter_label.pack(side=TOP, anchor=RIGHT)

        self._counter_value = ttk.Label(status_frame, text="0", style="CounterValue.TLabel")
        self._counter_value.pack(side=TOP, anchor=RIGHT)

        self._sync_status = ttk.Label(status_frame, text="", wraplength=200, foreground=ALERT_RED)
        self._sync_status.pack(side=TOP, pady=(10, 0))

        entry_frame = ttk.Labelframe(main, text="Scanner", padding=20)
        entry_frame.pack(fill=X)

        self._warning_label = ttk.Label(
            entry_frame,
            text="Zone auswählen!",
            font=("Helvetica", 18, "bold"),
            foreground=ALERT_RED,
        )
        self._warning_label.pack(pady=(0, 10))

        self._scan_var = ttk.StringVar()
        self._scan_entry = ttk.Entry(entry_frame, textvariable=self._scan_var, font=("Helvetica", 22))
        self._scan_entry.pack(fill=X)
        self._scan_entry.bind("<Return>", self._handle_scan)

        zone_frame = ttk.Labelframe(main, text="Zonen", padding=15)
        zone_frame.pack(fill=X, pady=(20, 0))

        zone_buttons = ttk.Frame(zone_frame)
        zone_buttons.pack(fill=X)

        first_row = ttk.Frame(zone_buttons)
        first_row.pack(fill=X, pady=5)

        self._zone_buttons: dict[str, ttk.Button] = {}
        for zone in ["A", "B", "C", "D"]:
            btn = ttk.Button(
                first_row,
                text=zone,
                style="Zone.TButton",
                command=lambda z=zone: self._set_zone(z),
                bootstyle="outline-primary",
                width=12,
            )
            btn.pack(side=LEFT, padx=5, expand=True, fill=X)
            self._zone_buttons[zone] = btn

        second_row = ttk.Frame(zone_buttons)
        second_row.pack(fill=X, pady=5)

        for zone in ["E-1", "E-2", "E-3", "E-4", "F"]:
            btn = ttk.Button(
                second_row,
                text=zone,
                style="WideZone.TButton",
                command=lambda z=zone: self._set_zone(z),
                bootstyle="outline-primary",
                width=12,
            )
            btn.pack(side=LEFT, padx=5, expand=True, fill=X)
            self._zone_buttons[zone] = btn

        finish_btn = ttk.Button(
            main,
            text="Fertig",
            command=self._finish_session,
            bootstyle="success",
            padding=15,
        )
        finish_btn.pack(pady=(30, 0))

    def _ensure_focus(self) -> None:
        if self._window.state() != "iconic":
            self._scan_entry.focus_set()
        self._window.after(500, self._ensure_focus)

    def _update_blink(self) -> None:
        if self._active_zone is None:
            self._blink_state = not self._blink_state
            self._warning_label.configure(
                text="Zone auswählen!",
                foreground=ALERT_RED if self._blink_state else WHITE,
            )
        else:
            self._warning_label.configure(foreground=PRIMARY_BLUE, text=f"Aktive Zone: {self._active_zone}")
        self._window.after(600, self._update_blink)

    def _set_zone(self, zone: str) -> None:
        self._active_zone = zone
        self._warning_label.configure(text=f"Aktive Zone: {zone}", foreground=PRIMARY_BLUE)
        self._highlight_zone_buttons(zone)

    def _handle_scan(self, event: object) -> None:
        value = self._scan_var.get().strip()
        if not value:
            return
        if self._active_zone is None:
            self._warning_label.configure(text="Zone auswählen!", foreground=ALERT_RED)
            self._scan_var.set("")
            return

        name = self._match_directory(value)
        timestamp = datetime.now().isoformat(timespec="seconds")
        self._db.upsert_package(value, self._active_zone, timestamp, name)
        self._scan_var.set("")
        self._scan_counter += 1
        self._update_counter_label()
        self._refresh_packages()

    def _match_directory(self, sendungsnr: str) -> Optional[str]:
        entries = self._db.get_directory_entries()
        if not entries:
            return None

        directory = [(row["sendungsnr"], row["name"]) for row in entries]
        matches = process.extract(
            sendungsnr,
            directory,
            processor=lambda item: item[0],
            scorer=fuzz.WRatio,
            limit=5,
        )
        if not matches:
            return None

        best_choice, best_score, _ = matches[0]
        collected: List[str] = []
        if best_score >= 90:
            collected.append(best_choice[1])
            for choice, score, _ in matches[1:]:
                if 85 <= score <= 95:
                    collected.append(choice[1])
        elif best_score >= 85:
            for choice, score, _ in matches:
                if 85 <= score <= 95:
                    collected.append(choice[1])
        if not collected:
            return None
        unique_names = sorted(set(filter(None, (name.strip() for name in collected))))
        return " / ".join(unique_names) if unique_names else None

    def _schedule_search_update(self, _event: object) -> None:
        if self._search_update_job is not None:
            self._window.after_cancel(self._search_update_job)
        self._search_update_job = self._window.after(250, self._refresh_packages)

    def _refresh_packages(self) -> None:
        query = self._search_var.get().strip()
        rows = self._db.get_all_packages()
        if query:
            filtered = []
            for row in rows:
                text_candidates = [row["sendungsnr"], row["zone"]]
                if row["name"]:
                    text_candidates.append(row["name"])
                score = max(
                    fuzz.WRatio(query, candidate)
                    for candidate in text_candidates
                    if candidate
                )
                if score >= 70:
                    filtered.append((score, row))
            filtered.sort(key=lambda item: item[0], reverse=True)
            display_rows = [item[1] for item in filtered]
        else:
            display_rows = rows

        for child in self._results.get_children():
            self._results.delete(child)

        for row in display_rows:
            self._results.insert(
                "",
                "end",
                values=(row["sendungsnr"], row["name"] or "", row["zone"], row["received_at"]),
            )

    def _update_counter_label(self) -> None:
        color = "green" if self._scan_counter > 0 else ALERT_RED
        self._counter_value.configure(text=str(self._scan_counter), foreground=color)

    def _finish_session(self) -> None:
        self._active_zone = None
        self._scan_counter = 0
        self._update_counter_label()
        self._warning_label.configure(text="Zone auswählen!", foreground=ALERT_RED)
        self._highlight_zone_buttons(None)

    def _show_sync_error(self, message: str) -> None:
        def update_label() -> None:
            self._sync_status.configure(text=f"Sync-Fehler: {message}")

        self._window.after(0, update_label)

    def _highlight_zone_buttons(self, active_zone: Optional[str]) -> None:
        for zone, button in self._zone_buttons.items():
            if active_zone is not None and zone == active_zone:
                button.configure(bootstyle="primary")
            else:
                button.configure(bootstyle="outline-primary")

    def _on_close(self) -> None:
        if self._sync_thread:
            self._sync_thread.stop()
            self._sync_thread.join(timeout=1)
        self._db.close()
        self._window.destroy()

    def run(self) -> None:
        self._window.mainloop()


def main() -> None:
    app = HermesApp()
    app.run()


if __name__ == "__main__":
    main()
