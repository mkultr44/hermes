# Hermes Paket-Zonen-Manager

Eine lokale Desktop-Anwendung zur schnellen Einbuchung von Paketen in Lagerzonen.

## Voraussetzungen

- Python 3.10 oder neuer
- Abhängigkeiten installieren:

```bash
pip install -r requirements.txt
```

## Starten

```bash
python app.py
```

Die Anwendung legt automatisch die SQLite-Datenbank `paket.db` im Projektverzeichnis an.

## Funktionen

- **Barcode-Scanner-Modus:** automatisches Fokussieren des Eingabefelds, Zone bleibt aktiv bis "Fertig".
- **Fuzzy-Suche:** durch RapidFuzz unterstützte Suche über Sendungsnummer, Name und Zone.
- **CSV-Synchronisation:** alle 30 Sekunden wird `hermes_final.csv` von der hinterlegten Nextcloud-Quelle geladen und die Directory-Tabelle aktualisiert.
- **Zonenverwaltung:** große, farbige Buttons für A–F (inkl. E-1 bis E-4) mit aktiver Hervorhebung.
- **Counter & Warnhinweise:** Live-Anzeige eingescannter Pakete, roter Hinweis bei fehlender Zonenauswahl.

## Datenbankstruktur

Die SQLite-Datenbank enthält zwei Tabellen:

- `packages(sendungsnr, zone, received_at, name)`
- `directory(sendungsnr, name, updated_at)`

## Beenden

Über den Button "Fertig" wird der Zähler zurückgesetzt und die aktive Zone aufgehoben. Beim Schließen des Fensters werden Synchronisations-Thread und Datenbankverbindung sauber beendet.
