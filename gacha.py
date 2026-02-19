import discord
from discord.ext import commands
import requests
import base64
import json
import random

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = "leetaiyi"
REPO_NAME = "DBot"
FILE_PATH = "gacha.json"

IMG_PATH = "https://raw.githubusercontent.com/leetaiyi/DBot/main/WM%20Gacha/"

API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

# =========================
# GITHUB FUNCTIONS
# =========================

def get_gacha_data():
    r = requests.get(API_URL, headers=headers)
    data = r.json()

    content = base64.b64decode(data["content"]).decode()
    return json.loads(content), data["sha"]

def update_gacha_data(new_data, sha):
    encoded = base64.b64encode(
        json.dumps(new_data, indent=2).encode()
    ).decode()

    payload = {
        "message": "Update gacha pulls",
        "content": encoded,
        "sha": sha
    }

    requests.put(API_URL, headers=headers, json=payload)

# =========================
# GACHA COMMAND
# =========================

@bot.command()
async def pull(ctx):
    data, sha = get_gacha_data()

    prizes = data["prizes"]
    users = data["users"]

    names = [p["name"] for p in prizes]
    weights = [p["weight"] for p in prizes]

    result = random.choices(names, weights=weights, k=1)[0]

    # Update user data
    user_id = str(ctx.author.id)

    if user_id not in users:
        users[user_id] = {}

    if result not in users[user_id]:
        users[user_id][result] = 0

    users[user_id][result] += 1

    update_gacha_data(data, sha)

    # Get image
    image_url = next(IMG_PATH + p["image"] for p in prizes if p["name"] == result)

    embed = discord.Embed(
        title="🎰 Gacha Pull!",
        description=f"{ctx.author.mention} pulled **{result}**!",
        color=discord.Color.gold()
    )

    embed.set_image(url=image_url)

    await ctx.send(embed=embed)

# =========================

bot.run(BOT_TOKEN)
