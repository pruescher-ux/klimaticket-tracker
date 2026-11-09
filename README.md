# 🚆 Klimaticket & Vorteilscard Journey Tracker

Eine mobile Web-App zur schnellen Erfassung deiner Bahn- und ÖPNV-Fahrten direkt in deiner Notion-Datenbank.

## Features
- **Echtzeit-Bahnhofsuche:** Autovervollständigung aller Bahnhöfe & Haltestellen über die offizielle HAFAS/Scotty-Schnittstelle.
- **Automatische Preisermittlung:**
  - **ÖBB Vorteilscard 66 (Classic):** 50% Rabatt auf Standard-Einzeltickets (Hauptrelationen & Kilometertarif-Berechnung).
  - **WESTbahn Vorteilspreis:** Automatische Tarifberechnung für Westbahn-Strecken.
  - **ÖPNV-Schnellwahl:** 1-Klick-Pauschalen für Wiener Linien (2,40 €), VVV, VOR.
  - **Freie Anpassung:** Vorgeschlagener Betrag kann vor dem Absenden jederzeit manuell editiert werden.
- **Notion Sync:** Schreibt Datum, Strecke, Abfahrt, Ziel, Betreiber, Fahrpreis, regulären Vollpreis und Notizen direkt in deine Notion-Datenbank.
- **Smartphone-optimiert:** PWA-kompatibel, lässt sich direkt als Web-App auf den Homescreen des Handys legen.

## Zugriff
- **Am Mac:** [http://localhost:8080](http://localhost:8080)
- **Am Smartphone (im selben WLAN):** [http://192.168.1.170:8080](http://192.168.1.170:8080)

## Server starten
```bash
cd /Users/peter/.gemini/antigravity/scratch/klimaticket-tracker
./run.sh
```
