# 🚆 Klimaticket & Vorteilscard Journey Tracker

Mobile Web-App zur schnellen Erfassung deiner Bahn- und ÖPNV-Fahrten direkt in deiner Notion-Datenbank.

## 🌐 Live-App (GitHub Pages)
Die App ist direkt über GitHub Pages öffentlich und mobil erreichbar:  
👉 **[https://pruescher-ux.github.io/klimaticket-tracker/](https://pruescher-ux.github.io/klimaticket-tracker/)**

*(Tipp für iOS/Android: Im Browser auf „Teilen“ bzw. Menü $\rightarrow$ **„Zum Home-Bildschirm hinzufügen“** tippen – schon hast du die Web-App wie eine native App als Icon auf deinem Handy).*

---

## Features
- **Echtzeit-Bahnhofsuche:** Autovervollständigung aller Bahnhöfe & Haltestellen über die offizielle HAFAS/Scotty-Schnittstelle (CORS-frei via JSONP).
- **Automatische Preisermittlung:**
  - **ÖBB Vorteilscard 66 (Classic):** 50% Rabatt auf Standard-Einzeltickets (Hauptrelationen & Kilometertarif-Berechnung).
  - **WESTbahn Vorteilspreis:** Automatische Tarifberechnung für Westbahn-Strecken.
  - **ÖPNV-Schnellwahl:** 1-Klick-Pauschalen für Wiener Linien (2,40 €), VVV, VOR.
  - **Freie Anpassung:** Vorgeschlagener Betrag kann vor dem Absenden jederzeit manuell editiert werden.
- **Notion Sync:** Schreibt Datum, Strecke, Abfahrt, Ziel, Betreiber, Fahrpreis, regulären Vollpreis und Notizen direkt in deine Notion-Datenbank.
- **100% Serverless / Client-Side:** Läuft komplett im Browser über GitHub Pages. Kein separater Server oder Mac notwendig.

---

## Lokaler Server (Optional)
Falls du die Python-Version lokal laufen lassen möchtest:
```bash
./run.sh
```
Aufruf unter [http://localhost:8080](http://localhost:8080).
