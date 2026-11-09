#!/usr/bin/env python3
"""
Klimaticket Journey Tracker & Notion Sync Server
Optimized for mobile access (Safari/Chrome on iOS & Android).
"""

import http.server
import socketserver
import urllib.request
import urllib.parse
import json
import ssl
import re
import math
import os
from datetime import date, datetime

PORT = int(os.environ.get("PORT", 8080))
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "ntn_Y5566151419AXV3YPYYMK4cyaVOIpNEdsjwTkWiJmul2TJ")
DATABASE_ID = os.environ.get("DATABASE_ID", "41314bc4-bafb-8167-a78e-c448c8b1b268")

# Try to load local .env if present
env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_file):
    try:
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() == "NOTION_TOKEN":
                        NOTION_TOKEN = v.strip()
                    elif k.strip() == "DATABASE_ID":
                        DATABASE_ID = v.strip()
                    elif k.strip() == "PORT":
                        PORT = int(v.strip())
    except Exception:
        pass

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

# Known key relations for high-accuracy pricing (Vollpreis & Vorteilspreis)
KNOWN_FARES = {
    ("wien", "salzburg"): {"oebb_vc66": 31.90, "oebb_full": 63.80, "west_vorteil": 36.90, "west_full": 69.90},
    ("wien", "linz"): {"oebb_vc66": 22.10, "oebb_full": 44.20, "west_vorteil": 22.90, "west_full": 44.00},
    ("wien", "st. pölten"): {"oebb_vc66": 6.90, "oebb_full": 13.80, "west_vorteil": 8.30, "west_full": 15.00},
    ("wien", "st. poelten"): {"oebb_vc66": 6.90, "oebb_full": 13.80, "west_vorteil": 8.30, "west_full": 15.00},
    ("wien", "amstetten"): {"oebb_vc66": 15.60, "oebb_full": 31.20, "west_vorteil": 16.50, "west_full": 31.00},
    ("wien", "wels"): {"oebb_vc66": 24.50, "oebb_full": 49.00, "west_vorteil": 26.50, "west_full": 49.00},
    ("wien", "attnang-puchheim"): {"oebb_vc66": 28.20, "oebb_full": 56.40, "west_vorteil": 30.50, "west_full": 57.00},
    ("wien", "innsbruck"): {"oebb_vc66": 44.20, "oebb_full": 88.40, "west_vorteil": 54.90, "west_full": 99.00},
    ("wien", "bregenz"): {"oebb_vc66": 49.30, "oebb_full": 98.60, "west_vorteil": 59.90, "west_full": 105.00},
    ("wien", "graz"): {"oebb_vc66": 23.70, "oebb_full": 47.40},
    ("wien", "klagenfurt"): {"oebb_vc66": 34.10, "oebb_full": 68.20},
    ("wien", "villach"): {"oebb_vc66": 35.80, "oebb_full": 71.60},
    ("salzburg", "linz"): {"oebb_vc66": 14.90, "oebb_full": 29.80, "west_vorteil": 16.50, "west_full": 29.00},
    ("salzburg", "innsbruck"): {"oebb_vc66": 25.80, "oebb_full": 51.60, "west_vorteil": 24.90, "west_full": 48.00},
    ("salzburg", "bregenz"): {"oebb_vc66": 39.20, "oebb_full": 78.40},
    ("bregenz", "dornbirn"): {"oebb_vc66": 1.90, "oebb_full": 3.80},
    ("bregenz", "feldkirch"): {"oebb_vc66": 4.30, "oebb_full": 8.60},
    ("bregenz", "bludenz"): {"oebb_vc66": 6.20, "oebb_full": 12.40},
    ("feldkirch", "innsbruck"): {"oebb_vc66": 21.40, "oebb_full": 42.80},
    ("dornbirn", "innsbruck"): {"oebb_vc66": 23.10, "oebb_full": 46.20},
    ("innsbruck", "kufstein"): {"oebb_vc66": 10.20, "oebb_full": 20.40, "west_vorteil": 11.50, "west_full": 21.00},
    ("graz", "linz"): {"oebb_vc66": 24.10, "oebb_full": 48.20},
    ("graz", "klagenfurt"): {"oebb_vc66": 16.80, "oebb_full": 33.60},
}

def clean_station_name(name: str) -> str:
    n = name.lower()
    for drop in ["hbf", "bahnhof", "bahnhst", "(u)", "[bhf/hst]", "westbahnhof", "hauptbahnhof"]:
        n = n.replace(drop, "")
    n = re.sub(r'\(.*?\)', '', n)
    return n.strip()

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def estimate_oebb_fare(distance_km: float):
    # Austrian rail detour factor approx 1.25x direct geodesic distance
    rail_dist = max(5.0, distance_km * 1.25)
    # Degressive tariff calculation
    if rail_dist <= 50:
        cost = 2.40 + (rail_dist * 0.22)
    elif rail_dist <= 150:
        cost = 2.40 + (50 * 0.22) + ((rail_dist - 50) * 0.19)
    elif rail_dist <= 300:
        cost = 2.40 + (50 * 0.22) + (100 * 0.19) + ((rail_dist - 150) * 0.15)
    else:
        cost = 2.40 + (50 * 0.22) + (100 * 0.19) + (150 * 0.15) + ((rail_dist - 300) * 0.12)

    full_price = round(cost, 1)
    vc66_price = round(full_price * 0.5, 1)
    # Standard format: ensure .x0 or .x5
    return max(2.40, vc66_price), max(4.80, full_price)

class RequestHandler(http.server.BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self.serve_app()
        elif path == "/api/stations":
            self.handle_stations(query)
        elif path == "/api/price":
            self.handle_price(query)
        elif path == "/api/history":
            self.handle_history()
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/save":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
                self.handle_save(data)
            except Exception as e:
                self.send_json({"error": f"Invalid payload: {str(e)}"}, status=400)
        else:
            self.send_error(404, "Not Found")

    def handle_stations(self, query):
        q = query.get('q', [''])[0].strip()
        if len(q) < 2:
            self.send_json([])
            return

        try:
            encoded = urllib.parse.quote(q)
            url = f"https://fahrplan.oebb.at/bin/ajax-getstop.exe/dn?start=1&tpl=suggest2json&REQ0JourneyStopsS0A=255&getstop=1&noSession=yes&REQ0JourneyStopsB=12&REQ0JourneyStopsS0F=select%21stopFinderPlugin%211&REQ0JourneyStopsS0G={encoded}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"})
            context = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=5, context=context) as response:
                raw = response.read().decode('iso-8859-1', errors='ignore')
                m = re.search(r'SLs\.sls\s*=\s*(\{.*?\});\s*SLs', raw, re.DOTALL)
                results = []
                if m:
                    data = json.loads(m.group(1))
                    for s in data.get("suggestions", []):
                        val = s.get("value", "").strip()
                        xcoord = s.get("xcoord", "")
                        ycoord = s.get("ycoord", "")
                        lon = float(xcoord) / 1000000.0 if xcoord else None
                        lat = float(ycoord) / 1000000.0 if ycoord else None
                        results.append({
                            "name": val,
                            "id": s.get("extId", ""),
                            "type": s.get("typeStr", ""),
                            "lat": lat,
                            "lon": lon
                        })
                self.send_json(results)
        except Exception as e:
            print("Station search error:", e)
            self.send_json([])

    def handle_price(self, query):
        origin = query.get('from', [''])[0].strip()
        dest = query.get('to', [''])[0].strip()
        operator = query.get('operator', ['ÖBB'])[0].strip()
        lat1 = float(query.get('lat1', [0])[0]) if query.get('lat1') else None
        lon1 = float(query.get('lon1', [0])[0]) if query.get('lon1') else None
        lat2 = float(query.get('lat2', [0])[0]) if query.get('lat2') else None
        lon2 = float(query.get('lon2', [0])[0]) if query.get('lon2') else None

        c_orig = clean_station_name(origin)
        c_dest = clean_station_name(dest)
        key1 = (c_orig, c_dest)
        key2 = (c_dest, c_orig)

        # Check known fare dictionary first
        known = KNOWN_FARES.get(key1) or KNOWN_FARES.get(key2)
        if known:
            if operator == "WESTbahn" and "west_vorteil" in known:
                self.send_json({
                    "price": known["west_vorteil"],
                    "full_price": known["west_full"],
                    "source": "WESTbahn Vorteilspreis Relation",
                    "operator": "WESTbahn"
                })
                return
            else:
                self.send_json({
                    "price": known["oebb_vc66"],
                    "full_price": known["oebb_full"],
                    "source": "ÖBB Vorteilscard 66 Relation",
                    "operator": operator
                })
                return

        # Special operator fixed prices
        if operator == "Wiener Linien":
            self.send_json({"price": 2.40, "full_price": 2.40, "source": "Wiener Linien Einzelfahrt", "operator": "Wiener Linien"})
            return
        if operator == "VOR":
            self.send_json({"price": 2.40, "full_price": 2.40, "source": "VOR Einzelfahrt", "operator": "VOR"})
            return
        if operator == "VVV":
            self.send_json({"price": 4.40, "full_price": 4.40, "source": "VVV Tagesticket/Einzelfahrt", "operator": "VVV"})
            return

        # Distance-based calculation if coordinates are present
        if lat1 and lon1 and lat2 and lon2:
            dist = haversine_km(lat1, lon1, lat2, lon2)
            vc66, full = estimate_oebb_fare(dist)
            if operator == "WESTbahn":
                # WESTbahn advantageous price estimate
                west_price = round(vc66 * 1.08, 1)
                west_full = round(full * 1.05, 1)
                self.send_json({
                    "price": west_price,
                    "full_price": west_full,
                    "distance_km": round(dist, 1),
                    "source": f"WESTbahn Schätzung (~{round(dist)} km)",
                    "operator": "WESTbahn"
                })
                return
            self.send_json({
                "price": vc66,
                "full_price": full,
                "distance_km": round(dist, 1),
                "source": f"ÖBB VC66 Kilometertarif (~{round(dist)} km)",
                "operator": operator
            })
            return

        # Fallback default
        self.send_json({"price": 0.0, "full_price": 0.0, "source": "Manuelle Eingabe", "operator": operator})

    def handle_save(self, data):
        origin = data.get("origin", "").strip()
        dest = data.get("destination", "").strip()
        trip_date = data.get("date", str(date.today()))
        operator = data.get("operator", "ÖBB")
        price = float(data.get("price", 0.0))
        full_price = float(data.get("full_price", price * 2 if operator == "ÖBB" else price))
        notes = data.get("notes", "").strip()

        if not origin or not dest:
            self.send_json({"error": "Start und Ziel dürfen nicht leer sein."}, status=400)
            return

        title = f"{origin} → {dest}"
        properties = {
            "Strecke": {
                "title": [{"type": "text", "text": {"content": title}}]
            },
            "Datum": {
                "date": {"start": trip_date}
            },
            "Abfahrt": {
                "rich_text": [{"type": "text", "text": {"content": origin}}]
            },
            "Ziel": {
                "rich_text": [{"type": "text", "text": {"content": dest}}]
            },
            "Betreiber": {
                "select": {"name": operator}
            },
            "Fahrpreis": {
                "number": round(price, 2)
            },
            "Regulärer Vollpreis": {
                "number": round(full_price, 2)
            }
        }
        if notes:
            properties["Notizen"] = {
                "rich_text": [{"type": "text", "text": {"content": notes}}]
            }

        payload = {
            "parent": {"database_id": DATABASE_ID},
            "properties": properties
        }

        req = urllib.request.Request(
            "https://api.notion.com/v1/pages",
            data=json.dumps(payload).encode('utf-8'),
            headers=NOTION_HEADERS,
            method="POST"
        )
        context = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, timeout=10, context=context) as response:
                res = json.loads(response.read().decode())
                self.send_json({"success": True, "id": res.get("id"), "title": title})
        except Exception as e:
            err_msg = str(e)
            if hasattr(e, 'read'):
                err_msg = e.read().decode()
            print("Notion save error:", err_msg)
            self.send_json({"error": err_msg}, status=500)

    def handle_history(self):
        url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
        payload = {
            "page_size": 8,
            "sorts": [{"property": "Datum", "direction": "descending"}]
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=NOTION_HEADERS, method="POST")
        context = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, timeout=10, context=context) as response:
                data = json.loads(response.read().decode())
                results = []
                total_savings = 0.0
                total_trips = len(data.get("results", []))
                for item in data.get("results", []):
                    props = item.get("properties", {})
                    title_list = props.get("Strecke", {}).get("title", [])
                    title = title_list[0].get("text", {}).get("content", "") if title_list else ""
                    dt = props.get("Datum", {}).get("date", {})
                    d_str = dt.get("start", "") if dt else ""
                    betr_obj = props.get("Betreiber", {}).get("select")
                    betr = betr_obj.get("name", "") if betr_obj else ""
                    price = props.get("Fahrpreis", {}).get("number") or 0.0
                    full_p = props.get("Regulärer Vollpreis", {}).get("number") or price

                    total_savings += price
                    results.append({
                        "id": item.get("id"),
                        "title": title,
                        "date": d_str,
                        "operator": betr,
                        "price": price,
                        "full_price": full_p
                    })
                self.send_json({"trips": results, "total_recent_savings": round(total_savings, 2)})
        except Exception as e:
            print("History query error:", e)
            self.send_json({"trips": [], "total_recent_savings": 0.0})

    def serve_app(self):
        html = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <title>Klimaticket Tracker</title>
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="theme-color" content="#0f172a">
  <link rel="apple-touch-icon" href="https://img.icons8.com/color/192/train.png">
  <style>
    :root {
      --bg: #0b1120;
      --card: #1e293b;
      --border: #334155;
      --primary: #38bdf8;
      --primary-hover: #0284c7;
      --accent: #10b981;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --oebb: #ef4444;
      --west: #3b82f6;
      --wl: #f97316;
    }
    * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
    body {
      margin: 0;
      padding: env(safe-area-inset-top, 16px) 16px env(safe-area-inset-bottom, 24px) 16px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    .container {
      width: 100%;
      max-width: 480px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 4px 4px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .brand-icon {
      width: 40px;
      height: 40px;
      border-radius: 12px;
      background: linear-gradient(135deg, #10b981 0%, #0284c7 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 22px;
      box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
    }
    h1 {
      font-size: 1.25rem;
      font-weight: 700;
      margin: 0;
      letter-spacing: -0.02em;
    }
    .badge {
      font-size: 0.72rem;
      padding: 3px 8px;
      background: rgba(56, 189, 248, 0.15);
      color: var(--primary);
      border-radius: 9999px;
      font-weight: 600;
      border: 1px solid rgba(56, 189, 248, 0.3);
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 18px;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }
    .field-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
      position: relative;
      margin-bottom: 12px;
    }
    label {
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .input-wrap {
      position: relative;
      display: flex;
      align-items: center;
    }
    input[type="text"], input[type="date"], input[type="number"], select {
      width: 100%;
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 12px;
      color: #fff;
      font-size: 1.05rem;
      padding: 13px 14px;
      outline: none;
      transition: border-color 0.15s, box-shadow 0.15s;
      -webkit-appearance: none;
    }
    input:focus, select:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.2);
    }
    .autocomplete-list {
      position: absolute;
      top: 100%;
      left: 0;
      right: 0;
      z-index: 100;
      background: #1e293b;
      border: 1px solid var(--border);
      border-radius: 12px;
      max-height: 220px;
      overflow-y: auto;
      margin-top: 4px;
      box-shadow: 0 12px 30px rgba(0, 0, 0, 0.5);
      display: none;
    }
    .autocomplete-item {
      padding: 12px 14px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid rgba(255,255,255,0.05);
      font-size: 0.95rem;
    }
    .autocomplete-item:active, .autocomplete-item:hover {
      background: #334155;
      color: var(--primary);
    }
    .autocomplete-item .type {
      font-size: 0.72rem;
      color: var(--text-muted);
    }
    .swap-btn {
      align-self: center;
      background: #334155;
      border: 1px solid var(--border);
      color: var(--primary);
      width: 38px;
      height: 38px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      margin: -6px auto 6px;
      box-shadow: 0 4px 8px rgba(0,0,0,0.2);
      transition: transform 0.2s;
    }
    .swap-btn:active {
      transform: scale(0.9) rotate(180deg);
    }
    .row {
      display: flex;
      gap: 10px;
    }
    .row > * { flex: 1; }

    /* Operator Chips */
    .operator-chips {
      display: flex;
      gap: 6px;
      overflow-x: auto;
      padding-bottom: 6px;
      margin-bottom: 12px;
      scrollbar-width: none;
    }
    .operator-chips::-webkit-scrollbar { display: none; }
    .chip {
      padding: 8px 14px;
      border-radius: 9999px;
      background: #0f172a;
      border: 1px solid var(--border);
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--text-muted);
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.15s;
    }
    .chip.active {
      background: var(--primary);
      color: #0b1120;
      border-color: var(--primary);
      box-shadow: 0 2px 8px rgba(56, 189, 248, 0.4);
    }
    .chip.oebb.active { background: var(--oebb); color: #fff; border-color: var(--oebb); }
    .chip.west.active { background: var(--west); color: #fff; border-color: var(--west); }
    .chip.wl.active { background: var(--wl); color: #fff; border-color: var(--wl); }

    /* Quick Presets for local transit */
    .preset-chips {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }
    .preset-btn {
      background: rgba(255, 255, 255, 0.05);
      border: 1px dashed var(--border);
      border-radius: 8px;
      color: var(--text-muted);
      font-size: 0.76rem;
      padding: 5px 10px;
      cursor: pointer;
    }
    .preset-btn:active {
      background: rgba(56, 189, 248, 0.2);
      color: var(--primary);
    }

    /* Price Box */
    .price-box {
      background: linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(56, 189, 248, 0.08) 100%);
      border: 1px solid rgba(16, 185, 129, 0.3);
      border-radius: 16px;
      padding: 14px;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .price-label {
      display: flex;
      flex-direction: column;
    }
    .price-label span:first-child {
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--accent);
      text-transform: uppercase;
    }
    .price-label span:last-child {
      font-size: 0.72rem;
      color: var(--text-muted);
    }
    .price-input-wrap {
      display: flex;
      align-items: center;
      gap: 6px;
      max-width: 140px;
    }
    .price-input-wrap input {
      font-size: 1.4rem;
      font-weight: 800;
      text-align: right;
      color: #10b981;
      padding: 8px 10px;
      border-color: rgba(16, 185, 129, 0.4);
    }
    .currency-symbol {
      font-size: 1.2rem;
      font-weight: 700;
      color: var(--accent);
    }

    /* Submit Button */
    .submit-btn {
      width: 100%;
      background: linear-gradient(135deg, #10b981 0%, #059669 100%);
      color: #ffffff;
      border: none;
      border-radius: 16px;
      font-size: 1.15rem;
      font-weight: 700;
      padding: 16px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      box-shadow: 0 8px 20px -4px rgba(16, 185, 129, 0.5);
      transition: transform 0.1s, opacity 0.2s;
    }
    .submit-btn:active {
      transform: scale(0.98);
      opacity: 0.9;
    }
    .submit-btn:disabled {
      background: #475569;
      box-shadow: none;
      cursor: not-allowed;
      opacity: 0.6;
    }

    /* Feedback Banner */
    .toast {
      position: fixed;
      top: 20px;
      left: 50%;
      transform: translateX(-50%) translateY(-100px);
      background: #10b981;
      color: #fff;
      padding: 12px 20px;
      border-radius: 12px;
      font-weight: 600;
      box-shadow: 0 10px 25px rgba(0,0,0,0.4);
      transition: transform 0.3s cubic-bezier(0.18, 0.89, 0.32, 1.28);
      z-index: 999;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .toast.show {
      transform: translateX(-50%) translateY(0);
    }

    /* Recent Trips List */
    .history-card {
      margin-top: 8px;
    }
    .history-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
    }
    .history-header h2 {
      font-size: 0.95rem;
      font-weight: 700;
      margin: 0;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .history-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 0;
      border-bottom: 1px solid rgba(255,255,255,0.06);
    }
    .history-item:last-child { border-bottom: none; }
    .history-title {
      font-size: 0.92rem;
      font-weight: 600;
      margin-bottom: 2px;
    }
    .history-meta {
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .history-price {
      font-size: 1rem;
      font-weight: 700;
      color: var(--accent);
      text-align: right;
    }
    .spinner {
      width: 20px;
      height: 20px;
      border: 3px solid rgba(255,255,255,0.3);
      border-top-color: #fff;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      display: none;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>

<div class="toast" id="toast">
  <span>✓</span> <span id="toastMsg">In Notion gespeichert!</span>
</div>

<div class="container">
  <header>
    <div class="brand">
      <div class="brand-icon">🚆</div>
      <div>
        <h1>Klimaticket Tracker</h1>
        <div style="font-size: 0.75rem; color: var(--text-muted);">ÖBB Vorteilscard 66 • WESTbahn</div>
      </div>
    </div>
    <div class="badge">Notion Sync</div>
  </header>

  <div class="card">
    <!-- Operator Choice -->
    <label>Betreiber / Transportmittel</label>
    <div class="operator-chips" id="operatorChips">
      <div class="chip oebb active" data-op="ÖBB">ÖBB</div>
      <div class="chip west" data-op="WESTbahn">WESTbahn</div>
      <div class="chip wl" data-op="Wiener Linien">Wiener Linien</div>
      <div class="chip" data-op="VVV">VVV</div>
      <div class="chip" data-op="VOR">VOR</div>
      <div class="chip" data-op="Sonstige">Sonstige</div>
    </div>

    <!-- Quick Presets -->
    <div class="preset-chips">
      <button type="button" class="preset-btn" onclick="applyPreset('Wiener Linien', 'Wien Kernzone', 'Wien Kernzone', 2.40)">+ Wiener Linien (2,40 €)</button>
      <button type="button" class="preset-btn" onclick="applyPreset('VVV', 'Vorarlberg', 'Vorarlberg', 4.40)">+ VVV Tag (4,40 €)</button>
      <button type="button" class="preset-btn" onclick="applyPreset('VOR', 'VOR Zone', 'VOR Zone', 2.40)">+ VOR Einzelfahrt (2,40 €)</button>
    </div>

    <!-- Origin Input -->
    <div class="field-group">
      <label>Abfahrt (Startbahnhof)</label>
      <div class="input-wrap">
        <input type="text" id="origin" placeholder="z.B. Wien Hbf, Bregenz, Salzburg..." autocomplete="off">
      </div>
      <div class="autocomplete-list" id="originList"></div>
    </div>

    <!-- Swap Button -->
    <button type="button" class="swap-btn" id="swapBtn" title="Richtung umkehren">⇄</button>

    <!-- Destination Input -->
    <div class="field-group">
      <label>Ziel (Zielbahnhof)</label>
      <div class="input-wrap">
        <input type="text" id="destination" placeholder="z.B. Salzburg Hbf, Linz, Dornbirn..." autocomplete="off">
      </div>
      <div class="autocomplete-list" id="destList"></div>
    </div>

    <div class="row">
      <!-- Date -->
      <div class="field-group">
        <label>Datum</label>
        <input type="date" id="tripDate">
      </div>
    </div>

    <!-- Price Section -->
    <div class="price-box">
      <div class="price-label">
        <span id="priceTitle">Fahrpreis (VC 66)</span>
        <span id="priceSubtitle">Automatisch ermittelt</span>
      </div>
      <div class="price-input-wrap">
        <input type="number" id="price" step="0.10" min="0" placeholder="0.00">
        <span class="currency-symbol">€</span>
      </div>
    </div>

    <!-- Notes -->
    <div class="field-group">
      <label>Notizen (optional)</label>
      <input type="text" id="notes" placeholder="z.B. RJX 62, Pendeln, Ausflug...">
    </div>

    <!-- Submit Button -->
    <button type="button" class="submit-btn" id="saveBtn">
      <div class="spinner" id="btnSpinner"></div>
      <span id="btnText">In Notion erfassen</span>
    </button>
  </div>

  <!-- Recent Entries from Notion -->
  <div class="card history-card">
    <div class="history-header">
      <h2>Letzte Notion Einträge</h2>
      <span id="recentSavingsBadge" class="badge">0,00 € Ersparnis</span>
    </div>
    <div id="historyList">
      <div style="text-align: center; color: var(--text-muted); font-size: 0.85rem; padding: 12px 0;">
        Lade Einträge...
      </div>
    </div>
  </div>
</div>

<script>
  let selectedOperator = 'ÖBB';
  let originCoords = null;
  let destCoords = null;
  let searchTimer = null;

  // Initialize date to today
  document.getElementById('tripDate').value = new Date().toISOString().split('T')[0];

  // Operator selection
  document.querySelectorAll('#operatorChips .chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('#operatorChips .chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      selectedOperator = chip.dataset.op;
      updatePriceTitle();
      triggerPriceCalc();
    });
  });

  function updatePriceTitle() {
    const title = document.getElementById('priceTitle');
    if (selectedOperator === 'ÖBB') {
      title.textContent = 'ÖBB Vorteilscard 66';
    } else if (selectedOperator === 'WESTbahn') {
      title.textContent = 'WESTbahn Vorteilspreis';
    } else {
      title.textContent = 'Fahrpreis';
    }
  }

  // Quick Preset Helper
  function applyPreset(op, from, to, price) {
    document.querySelectorAll('#operatorChips .chip').forEach(c => {
      c.classList.toggle('active', c.dataset.op === op);
    });
    selectedOperator = op;
    document.getElementById('origin').value = from;
    document.getElementById('destination').value = to;
    document.getElementById('price').value = price.toFixed(2);
    document.getElementById('priceSubtitle').textContent = 'Pauschalwert gesetzt';
    updatePriceTitle();
  }

  // Swap locations
  document.getElementById('swapBtn').addEventListener('click', () => {
    const origInput = document.getElementById('origin');
    const destInput = document.getElementById('destination');
    const tempVal = origInput.value;
    origInput.value = destInput.value;
    destInput.value = tempVal;

    const tempCoords = originCoords;
    originCoords = destCoords;
    destCoords = tempCoords;

    triggerPriceCalc();
  });

  // Autocomplete setup
  setupAutocomplete('origin', 'originList', coords => {
    originCoords = coords;
    triggerPriceCalc();
  });
  setupAutocomplete('destination', 'destList', coords => {
    destCoords = coords;
    triggerPriceCalc();
  });

  function setupAutocomplete(inputId, listId, onSelectCoords) {
    const input = document.getElementById(inputId);
    const list = document.getElementById(listId);

    input.addEventListener('input', () => {
      clearTimeout(searchTimer);
      const val = input.value.trim();
      if (val.length < 2) {
        list.style.display = 'none';
        return;
      }
      searchTimer = setTimeout(() => {
        fetch(`/api/stations?q=${encodeURIComponent(val)}`)
          .then(res => res.json())
          .then(data => {
            list.innerHTML = '';
            if (data.length === 0) {
              list.style.display = 'none';
              return;
            }
            data.forEach(item => {
              const div = document.createElement('div');
              div.className = 'autocomplete-item';
              div.innerHTML = `<span>${item.name}</span><span class="type">${item.type || 'Bhf'}</span>`;
              div.addEventListener('click', () => {
                input.value = item.name;
                list.style.display = 'none';
                if (item.lat && item.lon) {
                  onSelectCoords({ lat: item.lat, lon: item.lon });
                } else {
                  onSelectCoords(null);
                }
              });
              list.appendChild(div);
            });
            list.style.display = 'block';
          })
          .catch(() => { list.style.display = 'none'; });
      }, 250);
    });

    document.addEventListener('click', e => {
      if (!input.contains(e.target) && !list.contains(e.target)) {
        list.style.display = 'none';
      }
    });
  }

  // Trigger price calculation
  function triggerPriceCalc() {
    const from = document.getElementById('origin').value.trim();
    const to = document.getElementById('destination').value.trim();
    if (!from || !to) return;

    let url = `/api/price?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&operator=${encodeURIComponent(selectedOperator)}`;
    if (originCoords && destCoords) {
      url += `&lat1=${originCoords.lat}&lon1=${originCoords.lon}&lat2=${destCoords.lat}&lon2=${destCoords.lon}`;
    }

    fetch(url)
      .then(res => res.json())
      .then(data => {
        if (data.price && data.price > 0) {
          document.getElementById('price').value = data.price.toFixed(2);
          document.getElementById('priceSubtitle').textContent = data.source || 'Automatisch berechnet';
        }
      })
      .catch(err => console.error(err));
  }

  // Save to Notion
  document.getElementById('saveBtn').addEventListener('click', () => {
    const origin = document.getElementById('origin').value.trim();
    const dest = document.getElementById('destination').value.trim();
    const tripDate = document.getElementById('tripDate').value;
    const priceVal = parseFloat(document.getElementById('price').value) || 0.0;
    const notes = document.getElementById('notes').value.trim();

    if (!origin || !dest) {
      alert('Bitte Start und Ziel angeben.');
      return;
    }

    const saveBtn = document.getElementById('saveBtn');
    const spinner = document.getElementById('btnSpinner');
    const btnText = document.getElementById('btnText');

    saveBtn.disabled = true;
    spinner.style.display = 'block';
    btnText.textContent = 'Speichere in Notion...';

    const payload = {
      origin: origin,
      destination: dest,
      date: tripDate,
      operator: selectedOperator,
      price: priceVal,
      notes: notes
    };

    fetch('/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(res => res.json())
      .then(res => {
        saveBtn.disabled = false;
        spinner.style.display = 'none';
        btnText.textContent = 'In Notion erfassen';

        if (res.success) {
          showToast(`Erfasst: ${origin} → ${dest} (${priceVal.toFixed(2)} €)`);
          // Clear notes and reload history
          document.getElementById('notes').value = '';
          loadHistory();
        } else {
          alert('Fehler beim Speichern: ' + (res.error || 'Unbekannter Fehler'));
        }
      })
      .catch(err => {
        saveBtn.disabled = false;
        spinner.style.display = 'none';
        btnText.textContent = 'In Notion erfassen';
        alert('Netzwerkfehler: ' + err.message);
      });
  });

  function showToast(msg) {
    const toast = document.getElementById('toast');
    document.getElementById('toastMsg').textContent = msg;
    toast.classList.add('show');
    setTimeout(() => { toast.classList.remove('show'); }, 3000);
  }

  // Load Recent Notion Trips
  function loadHistory() {
    fetch('/api/history')
      .then(res => res.json())
      .then(data => {
        const list = document.getElementById('historyList');
        list.innerHTML = '';
        if (!data.trips || data.trips.length === 0) {
          list.innerHTML = '<div style="text-align: center; color: var(--text-muted); font-size: 0.85rem; padding: 12px 0;">Noch keine Fahrten erfasst.</div>';
          return;
        }

        document.getElementById('recentSavingsBadge').textContent = `${data.total_recent_savings.toFixed(2)} € Wert`;

        data.trips.forEach(item => {
          const div = document.createElement('div');
          div.className = 'history-item';
          div.innerHTML = `
            <div>
              <div class="history-title">${item.title}</div>
              <div class="history-meta">${item.date} • ${item.operator}</div>
            </div>
            <div class="history-price">${item.price.toFixed(2)} €</div>
          `;
          list.appendChild(div);
        });
      })
      .catch(() => {
        document.getElementById('historyList').innerHTML = '<div style="text-align:center; color: var(--text-muted);">Einträge konnten nicht geladen werden.</div>';
      });
  }

  // Initial history load
  loadHistory();
</script>
</body>
</html>
"""
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

def run():
    handler = RequestHandler
    with socketserver.TCPServer(("0.0.0.0", PORT), handler) as httpd:
        print(f"Server läuft auf http://0.0.0.0:{PORT}")
        print(f"Am Smartphone aufrufen via: http://192.168.1.170:{PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    run()
