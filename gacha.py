import discord
from discord.ext import commands
import requests
import base64
import json
import random
import os
from datetime import datetime, timezone

# =========================
# CONFIG
# =========================
ADMIN_IDS = {96408456294064128}

BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = "leetaiyi"
REPO_NAME = "DBot"
FILE_PATH = "prizes.json"

BASE_IMAGE_URL = "https://raw.githubusercontent.com/leetaiyi/DBot/main/WM%20Gacha/"

API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}?ref=main"

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

def today_string():
    return datetime.now(timezone.utc).date().isoformat()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

@bot.event
async def on_command_error(ctx, error):
    print("Command error:", error)

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
    users = data.setdefault("users", {})

    user_id = str(ctx.author.id)

    # Create user if missing
    if user_id not in users:
        users[user_id] = {
            "inventory": {},
            "coins": 1,
            "last_daily": today_string()
        }

    user = users[user_id]

    # Give daily coin if new day
    if user.get("last_daily") != today_string():
        user["coins"] += 1
        user["last_daily"] = today_string()

    # Check coins
    if user["coins"] <= 0:
        await ctx.send("❌ You have no coins! Come back tomorrow.")
        return

    # Deduct coin
    user["coins"] -= 1

    # Roll gacha
    names = [p["name"] for p in prizes]
    weights = [p["weight"] for p in prizes]

    result = random.choices(names, weights=weights, k=1)[0]

    # Update inventory
    inventory = user.setdefault("inventory", {})
    inventory[result] = inventory.get(result, 0) + 1

    update_gacha_data(data, sha)
    
    # Find the prize object with the name
    prize_obj = next((p for p in prizes if p["name"] == result), None)
    if prize_obj is None:
        await ctx.send(f"Error: prize '{result}' not found in JSON.")
        return

    image_file = prize_obj["image"]
    image_url = BASE_IMAGE_URL + image_file

    # Send embed
    embed = discord.Embed(
        title="🎰 Gacha Pull!",
        description=f"{ctx.author.mention} pulled **{result}**!\n🪙 Coins left: {user['coins']}",
        color=discord.Color.gold()
    )
    embed.set_image(url=image_url)

    await ctx.send(embed=embed)



def get_gacha_data():
    r = requests.get(API_URL, headers=headers)
    print("GitHub response:", r.json())  # <-- ADD THIS
    data = r.json()

    content = base64.b64decode(data["content"]).decode()
    return json.loads(content), data["sha"]

# =========================

@bot.command()
async def inventory(ctx):
    data, _ = get_gacha_data()
    users = data.get("users", {})

    user_id = str(ctx.author.id)

    if user_id not in users:
        await ctx.send("You have no pulls yet! Use `!pull` first.")
        return

    user = users[user_id]  # <-- get the user dict

    embed = discord.Embed(
        title=f"{ctx.author.display_name}'s Inventory",
        color=discord.Color.blue()
    )

    # Show coins
    embed.add_field(name="Coins", value=user.get("coins", 0), inline=False)

    inventory = user.get("inventory", {})

    if not inventory:
        embed.add_field(name="Inventory", value="You have no prizes yet!", inline=False)
    else:
        for prize, count in inventory.items():
            embed.add_field(name=prize, value=f"x{count}", inline=False)

    # Optional: total pulls
    total_pulls = sum(inventory.values())
    embed.set_footer(text=f"Total Pulls: {total_pulls}")

    await ctx.send(embed=embed)


@bot.command()
async def addcoin(ctx, member: discord.Member, amount: int = 1):
    if ctx.author.id not in ADMIN_IDS:
        await ctx.send("❌ You don't have permission to use this.")
        return

    data, sha = get_gacha_data()
    users = data.setdefault("users", {})

    user_id = str(member.id)

    if user_id not in users:
        users[user_id] = {
            "inventory": {},
            "coins": 0,
            "last_daily": today_string()
        }

    users[user_id]["coins"] += amount

    update_gacha_data(data, sha)

    await ctx.send(f"🪙 Gave {amount} coin(s) to {member.mention}.")


bot.run(BOT_TOKEN)
