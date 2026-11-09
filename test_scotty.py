import urllib.request
import urllib.parse
import re
import json
import ssl

def search_stations(query):
    encoded = urllib.parse.quote(query)
    url = f"https://fahrplan.oebb.at/bin/ajax-getstop.exe/dn?start=1&tpl=suggest2json&REQ0JourneyStopsS0A=7&getstop=1&noSession=yes&REQ0JourneyStopsB=10&REQ0JourneyStopsS0F=select%21stopFinderPlugin%211&REQ0JourneyStopsS0G={encoded}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"})
    context = ssl.create_default_context()
    with urllib.request.urlopen(req, context=context) as response:
        raw = response.read().decode('utf-8', errors='ignore')
        # Response format: SLs.sls={...};SLs.showSuggestion();
        m = re.search(r'SLs\.sls\s*=\s*(\{.*?\});\s*SLs', raw, re.DOTALL)
        if m:
            data = json.loads(m.group(1))
            suggestions = data.get("suggestions", [])
            results = []
            for s in suggestions:
                val = s.get("value", "")
                ext_id = s.get("extId", "")
                # Coordinates in Hafas are microdegrees: X=13045784 -> 13.045784, Y=47814370 -> 47.814370
                xcoord = s.get("xcoord", "")
                ycoord = s.get("ycoord", "")
                lon = float(xcoord) / 1000000.0 if xcoord else None
                lat = float(ycoord) / 1000000.0 if ycoord else None
                results.append({
                    "name": val,
                    "id": ext_id,
                    "type": s.get("typeStr", ""),
                    "lat": lat,
                    "lon": lon
                })
            return results
        return []

if __name__ == "__main__":
    for q in ["Wien", "Salzburg", "Bregenz", "Dornbirn"]:
        res = search_stations(q)
        print(f"Results for '{q}': {len(res)}")
        for r in res[:3]:
            print(" ", r)
