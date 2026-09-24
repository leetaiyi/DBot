# github.py

import requests
import base64
import json

from config import GITHUB_TOKEN

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}


def get_file(url):
    r = requests.get(url, headers=headers)
    r.raise_for_status()

    data = r.json()

    content = base64.b64decode(data["content"]).decode()
    return json.loads(content), data["sha"]


def update_file(url, data, sha):
    encoded = base64.b64encode(
        json.dumps(data, indent=2).encode()
    ).decode()

    payload = {
        "message": "Update bot data",
        "content": encoded,
        "sha": sha
    }

    r = requests.put(
        url,
        headers=headers,
        json=payload
    )

    r.raise_for_status()