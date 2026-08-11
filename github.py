# github.py

import requests
import base64
import json

from config import GITHUB_TOKEN
import asyncio

github_lock = asyncio.Lock()

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

    if r.status_code == 409:
        print("========== 409 DEBUG ==========")
        print("URL:", url)
        print("SHA we used:", sha)
        print("GitHub response:", r.text)

        # Immediately ask GitHub what the current SHA is
        current = requests.get(url, headers=headers)
        print("Current GET status:", current.status_code)

        if current.ok:
            current_data = current.json()
            print("CURRENT SHA:", current_data["sha"])

        print("===============================")

    r.raise_for_status()