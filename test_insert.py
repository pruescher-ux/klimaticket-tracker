import urllib.request
import json
import ssl
from datetime import date

NOTION_TOKEN = "ntn_Y5566151419AXV3YPYYMK4cyaVOIpNEdsjwTkWiJmul2TJ"
DATABASE_ID = "41314bc4-bafb-8167-a78e-c448c8b1b268"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def add_trip(origin, destination, trip_date, operator, price, full_price=None, notes=""):
    title = f"{origin} → {destination}"
    if full_price is None and operator == "ÖBB":
        full_price = round(price * 2, 2)
    elif full_price is None:
        full_price = price

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
            "rich_text": [{"type": "text", "text": {"content": destination}}]
        },
        "Betreiber": {
            "select": {"name": operator}
        },
        "Fahrpreis": {
            "number": price
        },
        "Regulärer Vollpreis": {
            "number": full_price
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
        headers=headers,
        method="POST"
    )
    context = ssl.create_default_context()
    with urllib.request.urlopen(req, context=context) as response:
        res = json.loads(response.read().decode())
        print(f"Added page: {res.get('id')}")
        return res

if __name__ == "__main__":
    res = add_trip("Wien Hbf", "Salzburg Hbf", str(date.today()), "ÖBB", 31.90, 63.80, "Test-Eintrag")
    # Archive test entry
    page_id = res['id']
    archive_req = urllib.request.Request(
        f"https://api.notion.com/v1/pages/{page_id}",
        data=json.dumps({"archived": True}).encode('utf-8'),
        headers=headers,
        method="PATCH"
    )
    context = ssl.create_default_context()
    with urllib.request.urlopen(archive_req, context=context) as response:
        print("Test-Eintrag erfolgreich bereinigt (archiviert)!")
