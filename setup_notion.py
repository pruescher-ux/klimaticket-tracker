import urllib.request
import json
import ssl

NOTION_TOKEN = "ntn_Y5566151419AXV3YPYYMK4cyaVOIpNEdsjwTkWiJmul2TJ"
PAGE_ID = "41314bc4-bafb-806b-8185-e9f57a20af5d"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

# Check if there are existing child databases or blocks
url_children = f"https://api.notion.com/v1/blocks/{PAGE_ID}/children"
req_children = urllib.request.Request(url_children, headers=headers)

context = ssl.create_default_context()
try:
    with urllib.request.urlopen(req_children, context=context) as response:
        children_data = json.loads(response.read().decode())
        print(f"Existing blocks: {len(children_data.get('results', []))}")
        for block in children_data.get('results', []):
            if block.get('type') == 'child_database':
                print(f"Found existing database: {block.get('id')} ({block.get('child_database', {}).get('title')})")
except Exception as e:
    print(f"Error checking children: {e}")

# Create database
create_db_url = "https://api.notion.com/v1/databases"
payload = {
    "parent": {
        "type": "page_id",
        "page_id": PAGE_ID
    },
    "title": [
        {
            "type": "text",
            "text": {
                "content": "Reisen & Ersparnisse"
            }
        }
    ],
    "properties": {
        "Strecke": {
            "title": {}
        },
        "Datum": {
            "date": {}
        },
        "Abfahrt": {
            "rich_text": {}
        },
        "Ziel": {
            "rich_text": {}
        },
        "Betreiber": {
            "select": {
                "options": [
                    {"name": "ÖBB", "color": "red"},
                    {"name": "WESTbahn", "color": "blue"},
                    {"name": "Wiener Linien", "color": "orange"},
                    {"name": "VVV", "color": "yellow"},
                    {"name": "VOR", "color": "green"},
                    {"name": "ÖPNV / Sonstige", "color": "gray"}
                ]
            }
        },
        "Fahrpreis": {
            "number": {
                "format": "euro"
            }
        },
        "Regulärer Vollpreis": {
            "number": {
                "format": "euro"
            }
        },
        "Notizen": {
            "rich_text": {}
        }
    }
}

req_db = urllib.request.Request(create_db_url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
try:
    with urllib.request.urlopen(req_db, context=context) as response:
        result = json.loads(response.read().decode())
        print("Database created successfully!")
        print("Database ID:", result.get("id"))
except Exception as e:
    print(f"Error creating database: {e}")
    if hasattr(e, 'read'):
        print(e.read().decode())
