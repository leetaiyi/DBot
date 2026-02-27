import discord
from discord.ext import commands
import requests
import base64
import json
import random
import os
from datetime import datetime, timezone, UTC, timedelta
from keep_alive import keep_alive

# Re-pull code from GitHub
import os

os.system("git pull origin main --no-ff")

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
FILE_PATH = "prizes.json"

PITY_LIM = 5

BASE_IMAGE_URL = "https://raw.githubusercontent.com/leetaiyi/DBot/main/WM%20Gacha/"

API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}?ref=main"

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


def next_midnight_unix():
    now = datetime.now(UTC)
    next_midnight = (now + timedelta(days=1)).replace(hour=0,
                                                      minute=0,
                                                      second=0,
                                                      microsecond=0)
    return int(next_midnight.timestamp())


def today_string():
    return datetime.now(timezone.utc).date().isoformat()


@bot.check
async def globally_block_dms_and_wrong_channels(ctx):
    return ctx.channel.id in ALLOWED_CHANNELS


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")


# Cooldown error
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(
            f"⏳ The gacha is busy! Please wait {error.retry_after:.1f} seconds before pulling again."
        )
    else:
        print(error)  # Other errors


# =========================
# GITHUB FUNCTIONS
# =========================


def get_gacha_data():
    r = requests.get(API_URL, headers=headers)
    print("GitHub response:", r.json())  # <-- ADD THIS
    data = r.json()

    content = base64.b64decode(data["content"]).decode()
    return json.loads(content), data["sha"]


def update_gacha_data(new_data, sha):
    encoded = base64.b64encode(json.dumps(new_data,
                                          indent=2).encode()).decode()

    payload = {"message": "Update gacha pulls", "content": encoded, "sha": sha}

    requests.put(API_URL, headers=headers, json=payload)


# =========================
# GACHA COMMAND
# =========================


@bot.command()
@commands.cooldown(rate=1, per=10.0, type=commands.BucketType.default)
async def pull(ctx):
    data, sha = get_gacha_data()

    prizes = data["prizes"]
    users = data.setdefault("users", {})

    user_id = str(ctx.author.id)

    # FIRST TIME USER — give starter coins
    if user_id not in users:
        users[user_id] = {
            "coins": 5,  # starter bonus
            "inventory": {},
            "last_coin_date": today_string(),
            "pity_counter": 0,
            "pulls": 0
        }

        await ctx.send(
            f"🎁 Welcome {ctx.author.mention}! You received **5 starter WMGpeSOs!**"
        )

    user = users[user_id]

    daily_coin_used = False

    # Give daily coin if new day
    if user.get("last_daily") != today_string():
        user["coins"] += 1
        user["last_daily"] = today_string()
        daily_coin_used = True

    # Check coins
    if user["coins"] <= 0:
        next_reset = next_midnight_unix()

        await ctx.send(f"❌ You have no coins!\n"
                       f"⏳ Next coin <t:{next_reset}:R>")
        return

    # Deduct coin
    user["coins"] -= 1

    # Roll gacha
    inventory = user.setdefault("inventory", {})
    user["pity"] = user.get("pity", 0) + 1

    # Find prizes user doesn't own yet
    unowned_prizes = [p for p in prizes if p["name"] not in inventory]

    pity_pool = [p for p in unowned_prizes if p["weight"] != 1]

    # Pity trigger
    if user["pity"] >= PITY_LIM and pity_pool:
        # Force new item
        names = [p["name"] for p in pity_pool]
        weights = [p["weight"] for p in pity_pool]

        result = random.choices(names, weights=weights, k=1)[0]
        user["pity"] = 0  # Reset pity

        pity_triggered = True
    else:
        names = [p["name"] for p in prizes]
        weights = [p["weight"] for p in prizes]

        result = random.choices(names, weights=weights, k=1)[0]

        # Reset pity if new item obtained naturally
        if result not in inventory:
            user["pity"] = 0

        pity_triggered = False

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
    # Determine rarity
    weight = prize_obj["weight"]

    rarity_message = ""
    embed_color = discord.Color.gold()

    if weight == 1:
        rarity_message = "🚨🔥🚨🔥🚨 **LUDICROUSLY RARE!!!** 🚨🔥🚨🔥🚨"
        embed_color = discord.Color.gold()
    elif weight <= 5:
        rarity_message = "🌟🌟🌟 **ULTRA RARE!!** 🌟🌟🌟"
        embed_color = discord.Color.purple()
    elif weight <= 25:
        rarity_message = "✨ **RARE!** ✨"
        embed_color = discord.Color.blue()

    description = f"{ctx.author.mention} pulled **{result}**!\n{rarity_message}\n\n🪙 Coins left: {user['coins']}"

    if daily_coin_used:
        description += "\n🌅 Daily pull used!"

    # Build embed
    embed = discord.Embed(title="🎰 Gacha Pull!",
                          description=description,
                          color=embed_color)

    embed.set_image(url=image_url)

    await ctx.send(embed=embed)


# =========================


@bot.command()
async def inventory(ctx):
    import discord

    data, _ = get_gacha_data()

    prizes = data.get("prizes", [])
    users = data.get("users", {})

    user_id = str(ctx.author.id)

    # Check if user exists
    if user_id not in users:
        await ctx.send("You have no pulls yet! Use `!pull` first.")
        return

    user = users[user_id]

    inventory = user.get("inventory", {})
    coins = user.get("coins", 0)

    # Create weight lookup
    weight_map = {p["name"]: p["weight"] for p in prizes}

    # Create rarity categories
    categories = {
        "🔥 Ludicrous": [],
        "🌟 Ultra Rare": [],
        "✨ Rare": [],
        "Common": []
    }

    # Categorize items
    for prize, count in inventory.items():
        weight = weight_map.get(prize, 9999)
        entry = f"{prize} x{count}"

        if weight == 1:
            categories["🔥 Ludicrous"].append(entry)
        elif weight <= 5:
            categories["🌟 Ultra Rare"].append(entry)
        elif weight <= 25:
            categories["✨ Rare"].append(entry)
        else:
            categories["Common"].append(entry)

    # Sort alphabetically within each category
    for category in categories:
        categories[category].sort()

    # Build embed
    embed = discord.Embed(title=f"{ctx.author.display_name}'s Inventory",
                          color=discord.Color.blue())

    # Coins field
    embed.add_field(name="🪙 WMGpeSos", value=str(coins), inline=False)

    # Add each category if it has items
    has_items = False
    for category, items in categories.items():
        if items:
            embed.add_field(name=category,
                            value="\n".join(items),
                            inline=False)
            has_items = True

    # If empty inventory
    if not has_items:
        embed.add_field(name="Inventory",
                        value="You have no prizes yet!",
                        inline=False)

    # Total pulls
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

    await ctx.send(f"🪙 Gave {amount} WMGpeSO(s) to {member.mention}.")


keep_alive()

BOT_TOKEN = os.environ["BOT_TOKEN"]
bot.run(BOT_TOKEN)
