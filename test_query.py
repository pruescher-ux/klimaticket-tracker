import urllib.request
import json
import ssl

NOTION_TOKEN = "ntn_Y5566151419AXV3YPYYMK4cyaVOIpNEdsjwTkWiJmul2TJ"
DATABASE_ID = "41314bc4-bafb-8167-a78e-c448c8b1b268"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def query_recent_entries():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {
        "page_size": 10,
        "sorts": [
            {
                "property": "Datum",
                "direction": "descending"
            }
        ]
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
    context = ssl.create_default_context()
    with urllib.request.urlopen(req, context=context) as response:
        data = json.loads(response.read().decode())
        print(f"Total entries in DB: {len(data.get('results', []))}")
        return data.get('results', [])

if __name__ == "__main__":
    query_recent_entries()
