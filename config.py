# config.py
import os

# =========================
# CONFIG
# =========================
ALLOWED_CHANNELS = {
    1476061562404995213,  #Ramajohns #ctl-sandbox
    1474234316019073064,  #WMGSO #gacha-bot
    1473837591974645932  #CTLnF #bottest
}

ADMIN_IDS = {
    96408456294064128,  #ctl
    156937687515791361  #ben
}

BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = "leetaiyi"
REPO_NAME = "DBot"

PITY_LIM = 5

BASE_IMAGE_URL = "https://raw.githubusercontent.com/leetaiyi/DBot/data/WM%20Gacha/"

PRIZES_PATH = "prizes.json"
USERS_PATH = "users.json"

PRIZES_URL = (
    f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
    f"/contents/{PRIZES_PATH}"
)

USERS_URL = (
    f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
    f"/contents/{USERS_PATH}"
)

DATA_BRANCH = "data"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}
