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

PITY_LIM = 3

BASE_IMAGE_URL = "https://raw.githubusercontent.com/leetaiyi/DBot/data/WM%20Gacha/"

PRIZES_PATH = "prizes.json"
USERS_PATH = "users.json"

PRIZES_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{PRIZES_PATH}?ref=data"
USERS_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{USERS_PATH}?ref=data"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
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


# Pause function
paused_until = None


def is_paused():
    global paused_until
    if paused_until is None:
        return False

    return datetime.now(UTC) < paused_until


# Achievement helpers
def effective_item_count(inventory, claims_used, requirement):
    if isinstance(requirement, list):
        return max(
            inventory.get(item, 0) - claims_used
            for item in requirement
        )

    return inventory.get(requirement, 0) - claims_used

def achievement_remaining_progress(inventory, claims_used, items):
    counts = [
        max(0, effective_item_count(inventory, claims_used, req))
        for req in items
    ]

    completed_parts = sum(c > 0 for c in counts)

    return completed_parts, len(items), min(counts)



@bot.check
async def global_pause_check(ctx):
    global paused_until

    # Always allow resume command
    if ctx.command and ctx.command.name == "resume":
        return True

    # If not paused, allow commands
    if paused_until is None:
        return True

    # If pause expired, clear it and allow commands
    if datetime.now(UTC) >= paused_until:
        paused_until = None
        return True

    # Otherwise block
    unix = int(paused_until.timestamp())
    await ctx.send(f"⏸️ Bot is paused. Resumes <t:{unix}:R>")
    return False


def check_item_group(inventory, requirement):
    if isinstance(requirement, list):
        return any(item in inventory for item in requirement)
    return requirement in inventory


def count_progress(inventory, items):
    progress = sum(check_item_group(inventory, r) for r in items)
    return progress, len(items)


def is_complete(inventory, items):
    return all(check_item_group(inventory, r) for r in items)


# =========================
# GITHUB FUNCTIONS
# =========================


def get_file(url):
    r = requests.get(url, headers=headers)
    data = r.json()

    if "content" not in data:
        print("GitHub ERROR:", data)
        raise Exception("Failed to fetch file")

    content = base64.b64decode(data["content"]).decode()
    return json.loads(content), data["sha"]


def update_file(url, new_data, sha):
    encoded = base64.b64encode(json.dumps(new_data, indent=2).encode()).decode()

    payload = {
        "message": "Update data",
        "content": encoded,
        "sha": sha,
        "branch": "data"
    }

    r = requests.put(url, headers=headers, json=payload)

    if r.status_code != 200:
        print("Update failed:", r.json())


# =========================
# GACHA COMMAND
# =========================


@bot.command()
@commands.cooldown(rate=1, per=10.0, type=commands.BucketType.default)
async def pull(ctx):
    prize_data, _ = get_file(PRIZES_URL)
    user_data, user_sha = get_file(USERS_URL)

    prizes = prize_data["prizes"]
    users = user_data.setdefault("users", {})

    user_id = str(ctx.author.id)

    # FIRST TIME USER — give starter coins
    if user_id not in users:
        users[user_id] = {
            "coins": 5,  # starter bonus
            "inventory": {},
            "last_daily": today_string(),
            "pity": 0,
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
        # Hidden stat: attempted to pull with no coins
        user["impatience"] = user.get("impatience", 0) + 1

        update_file(USERS_URL, user_data, user_sha)
        
        next_reset = next_midnight_unix()

        await ctx.send(f"❌ You have no WMGpeSOs!\n"
                       f"⏳ Next daily <t:{next_reset}:R>")
        return

    # Deduct coin
    user["coins"] -= 1

    # Roll gacha
    inventory = user.setdefault("inventory", {})
    user["pity"] = user.get("pity", 0) + 1

    # Ensure blessed exists
    if "blessed" not in user:
        user["blessed"] = False

    # Check blessing
    if user["blessed"]:
        # Only allow weight <= 5
        blessed_prizes = [p for p in prizes if p["weight"] <= 5]

        names = [p["name"] for p in blessed_prizes]
        weights = [p["weight"] for p in blessed_prizes]

        result = random.choices(names, weights=weights, k=1)[0]

        user["blessed"] = False  # consume blessing

        if result not in inventory:
            user["pity"] = 0
    elif user["pity"] >= PITY_LIM:
        # Find prizes user doesn't own yet
        unowned_prizes = [p for p in prizes if p["name"] not in inventory]

        pity_pool = [p for p in unowned_prizes if p["weight"] != 1]
        if pity_pool:
            # Pity trigger
            # Force new item
            names = [p["name"] for p in pity_pool]
            weights = [p["weight"] for p in pity_pool]

            result = random.choices(names, weights=weights, k=1)[0]
            user["pity"] = 0  # Reset pity
        else:
            names = [p["name"] for p in prizes]
            weights = [p["weight"] for p in prizes]

            result = random.choices(names, weights=weights, k=1)[0]
            # Reset pity if new item obtained naturally
            if result not in inventory:
                user["pity"] = 0

    else:
        names = [p["name"] for p in prizes]
        weights = [p["weight"] for p in prizes]

        result = random.choices(names, weights=weights, k=1)[0]

        # Reset pity if new item obtained naturally
        if result not in inventory:
            user["pity"] = 0

    # Update inventory
    inventory = user.setdefault("inventory", {})
    inventory[result] = inventory.get(result, 0) + 1

    update_file(USERS_URL, user_data, user_sha)

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

    description = f"{ctx.author.mention} pulled **{result}**!\n{rarity_message}\n\n🪙 WMGpeSOs left: {user['coins']}"

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

    prize_data, _ = get_file(PRIZES_URL)
    user_data, _ = get_file(USERS_URL)

    prizes = prize_data["prizes"]
    users = user_data.get("users", {})
    claims = user.setdefault("achievement_claims", {})

    user_id = str(ctx.author.id)

    # Check if user exists
    if user_id not in users:
        await ctx.send("You have no pulls yet! Use `!pull` first.")
        return

    user = users[user_id]

    inventory = user.get("inventory", {})
    coins = user.get("coins", 0)
    claims = user.get("achievement_claims", {})

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

    # Daily message
    if user.get("last_daily") != today_string():
        embed.add_field(name="🎁 Daily WMGpeSO Available!",
                        value="Use `!pull` to claim your free daily pull.",
                        inline=False)

    # Coins field
    embed.add_field(name="🪙 WMGpeSOs", value=str(coins), inline=False)

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

    # Achievement redemptions
    if claims:
        achievement_lines = []

        for achievement_name, count in sorted(claims.items()):
            if count > 0:
                achievement_lines.append(f"{achievement_name} x{count}")

        if achievement_lines:
            embed.add_field(
                name="🏆 Achievements",
                value="\n".join(achievement_lines),
                inline=False
            )

    # Total pulls
    total_pulls = sum(inventory.values())
    embed.set_footer(text=f"Total Pulls: {total_pulls}")

    await ctx.send(embed=embed)


@bot.command()
async def addcoin(ctx, member: discord.Member, amount: int = 1):
    if ctx.author.id not in ADMIN_IDS:
        await ctx.send("❌ You don't have permission to use this.")
        return

    user_data, user_sha = get_file(USERS_URL)
    users = user_data.setdefault("users", {})

    user_id = str(member.id)

    if user_id not in users:
        users[user_id] = {
            "inventory": {},
            "coins": 0,
            "last_daily": today_string(),
            "pity": 0
        }

    users[user_id]["coins"] += amount

    update_file(USERS_URL, user_data, user_sha)

    await ctx.send(f"🪙 Gave {amount} WMGpeSO(s) to {member.mention}.")


@bot.command()
@commands.has_permissions(administrator=True)
async def pause(ctx, minutes: int):
    global paused_until

    if minutes <= 0:
        await ctx.send("❌ Minutes must be positive.")
        return

    paused_until = datetime.now(UTC) + timedelta(minutes=minutes)

    unix = int(paused_until.timestamp())

    await ctx.send(f"⏸️ Bot paused for **{minutes} minutes**.\n"
                   f"Resumes <t:{unix}:R>")


@bot.command()
@commands.has_permissions(administrator=True)
async def resume(ctx):
    global paused_until
    paused_until = None
    await ctx.send("▶️ Bot resumed.")


@bot.command()
async def bless(ctx, member: discord.Member):
    if ctx.author.id not in ADMIN_IDS:
        await ctx.send("❌ You cannot bless.")
        return

    user_data, user_sha = get_file(USERS_URL)
    users = user_data.setdefault("users", {})

    user_id = str(member.id)

    if user_id not in users:
        users[user_id] = {
            "coins": 0,
            "inventory": {},
            "last_daily": None,
            "pity_counter": 0,
            "pulls": 0
        }

    users[user_id]["blessed"] = True

    update_file(USERS_URL, user_data, user_sha)

    await ctx.send(
        f"✨ {member.mention} has been **blessed**! Their next pull will be Ultra Rare or better."
    )


@bot.command()
async def achievements(ctx):
    prize_data, _ = get_file(PRIZES_URL)
    user_data, _ = get_file(USERS_URL)

    achievements = prize_data.get("achievements", {})
    users = user_data.get("users", {})

    user_id = str(ctx.author.id)

    if user_id not in users:
        await ctx.send("You have no progress yet! Use `!pull` first.")
        return

    inventory = users[user_id].get("inventory", {})

    embed = discord.Embed(
        title=f"{ctx.author.display_name}'s Achievements",
        color=discord.Color.dark_gold()
    )

    for name, info in achievements.items():
        items = info["items"]
        rarity = info.get("rarity", "common")

        complete = is_complete(inventory, items)
        progress, total = count_progress(inventory, items)

        # Skip achievements with zero progress
        if progress == 0:
            continue

        # Hide rare achievements unless complete
        if rarity != "common" and not complete:
            display_name = "❓ Hidden Achievement"
            owned = []
            for req in items:
                if check_item_group(inventory, req):
                    owned.append(req)

            value = f"Obtained: {', '.join(owned)}"

        else:
            display_name = name

            if complete:
                value = "✅ Completed!"
            else:
                missing = []
                for req in items:
                    if not check_item_group(inventory, req):
                        if isinstance(req, list):
                            missing.append(req[0])
                        else:
                            missing.append(req)

                value = f"Progress: {progress}/{total}\nMissing: {', '.join(missing)}"

        embed.add_field(name=display_name, value=value, inline=False)

    if len(embed.fields) == 0:
        embed.description = "No achievements in progress yet. Start pulling! 🎰"

    await ctx.send(embed=embed)


@bot.command()
async def acheivements(ctx):
    await ctx.send("I before E except after C")


@bot.command()
async def redeem(ctx, *, achievement_name):
    # Load files
    prize_data, _ = get_file(PRIZES_URL)
    user_data, user_sha = get_file(USERS_URL)

    achievements = prize_data.get("achievements", {})
    users = user_data.setdefault("users", {})

    user_id = str(ctx.author.id)

    # User check
    if user_id not in users:
        await ctx.send("❌ You have no inventory yet.")
        return

    # Achievement exists?
    if achievement_name not in achievements:
        await ctx.send("❌ Achievement not found.")
        return

    achievement = achievements[achievement_name]

    inventory = users[user_id].setdefault("inventory", {})
    claims = users[user_id].setdefault("achievement_claims", {})

    items = achievement["items"]

    # Reward structure
    reward = achievement.get("reward")

    if reward is None:
        await ctx.send("❌ This achievement has no reward configured. (Help suggest one)")
        return

    reward_name = reward["name"]
    reward_image = reward["image"]

    # Number already redeemed
    claimed_count = claims.get(achievement_name, 0)

    # Compute redeemability
    effective_counts = []

    for req in items:

        # Any-of group
        if isinstance(req, list):

            remaining = max(
                inventory.get(item, 0) - claimed_count
                for item in req
            )

        else:
            remaining = inventory.get(req, 0) - claimed_count

        effective_counts.append(max(0, remaining))

    redeemable = min(effective_counts)

    # Must have a full redeemable set
    if redeemable <= 0:
        await ctx.send(
            "❌ You do not currently have a full redeemable set."
        )
        return

    # Grant reward
    inventory[reward_name] = inventory.get(reward_name, 0) + 1

    # Track redemption
    claims[achievement_name] = claimed_count + 1

    # Save
    update_file(USERS_URL, user_data, user_sha)

    # Embed
    image_url = BASE_IMAGE_URL + reward_image

    embed = discord.Embed(
        title="🏆 Achievement Redeemed!",
        description=(
            f"{ctx.author.mention} redeemed "
            f"**{achievement_name}**!\n\n"
            f"🎁 Received **{reward_name}**!"
        ),
        color=discord.Color.dark_gold()
    )

    embed.set_image(url=image_url)

    await ctx.send(embed=embed)

# =========================
# QUIZ FUNCTIONS
# =========================

KEYS = [
    ["C", "A", 0],
    ["F", "D", -1],
    ["Bb", "G", -2],
    ["Eb", "C", -3],
    ["Ab", "F", -4],
    ["Db", "Bb", -5],
    ["Gb", "Eb", -6],
    ["Cb", "Ab", -7],
    ["G", "E", 1],
    ["D", "B", 2],
    ["A", "F#", 3],
    ["E", "C#", 4],
    ["B", "G#", 5],
    ["F#", "D#", 6],
    ["C#", "A#", 7],
]

QUESTION_TEXT = {
    (0, 1): lambda k: f"What is the relative minor of {k[0]} major?",
    (1, 0): lambda k: f"What is the relative major of {k[1]} minor?",
    (0, 2): lambda k: (
        f"How many {'sharps' if k[2] < 0 else 'flats'} "
        f"does {k[0]} major have?"
        if k[2] != 0
        else f"How many accidentals does {k[0]} major have?"
    ),
    (1, 2): lambda k: (
        f"How many {'sharps' if k[2] < 0 else 'flats'} "
        f"does {k[1]} minor have?"
        if k[2] != 0
        else f"How many accidentals does {k[1]} minor have?"
    ),
    (2, 0): lambda k: (
        f"What major key has {abs(k[2])} "
        f"{'sharp' if abs(k[2]) == 1 else 'sharps'}?"
        if k[2] < 0 else
        f"What major key has {k[2]} "
        f"{'flat' if k[2] == 1 else 'flats'}?"
    ),
    (2, 1): lambda k: (
        f"What relative minor has {abs(k[2])} "
        f"{'sharp' if abs(k[2]) == 1 else 'sharps'}?"
        if k[2] < 0 else
        f"What relative minor has {k[2]} "
        f"{'flat' if k[2] == 1 else 'flats'}?"
    )
}

@bot.command()
async def quiz(ctx):
    user_data, user_sha = get_file(USERS_URL)

    users = user_data.setdefault("users", {})
    user_id = str(ctx.author.id)

    if user_id not in users:
        await ctx.send("Use `!pull` first to initialize your account.")
        return

    user = users[user_id]

    today = today_string()

    # Already has today's quiz
    quiz = user.get("daily_quiz")
    if quiz is not None and quiz.get("date") == today:
        if quiz.get("completed"):
            await ctx.send("✅ You've already completed today's quiz.")
        else:
            key = KEYS[quiz["key_index"]]
            reference, asked = quiz["question"]
            prompt = QUESTION_TEXT[(reference, asked)](key)

            await ctx.send(
                f"🎼 **You already have today's quiz:**\n\n{prompt}"
            )
        return

    # Generate new quiz
    key_index = random.randrange(len(KEYS))

    reference = random.randint(0, 2)
    asked = random.randint(0, 2)
    while asked == reference:
        asked = random.randint(0, 2)

    user["daily_quiz"] = {
        "date": today,
        "key_index": key_index,
        "question": [reference, asked],
        "completed": False
    }

    update_file(USERS_URL, user_data, user_sha)

    key = KEYS[key_index]
    prompt = QUESTION_TEXT[(reference, asked)](key)

    await ctx.send(
        f"🎼 **Daily Music Theory Quiz**\n\n"
        f"{prompt}\n\n"
        f"Reply using `!answer <answer>`."
    )


@bot.command()
async def answer(ctx, *, response):
    user_data, user_sha = get_file(USERS_URL)

    users = user_data.setdefault("users", {})
    user_id = str(ctx.author.id)

    if user_id not in users:
        await ctx.send("Use `!pull` first to initialize your account.")
        return

    user = users[user_id]

    quiz = user.get("daily_quiz")

    if quiz is None or quiz.get("date") != today_string():
        await ctx.send(
            "You don't have today's quiz.\n"
            "Use `!quiz` first."
        )
        return

    if quiz.get("completed"):
        await ctx.send("You've already completed today's quiz.")
        return

    key = KEYS[quiz["key_index"]]
    reference, asked = quiz["question"]

    # Determine correct answer
    if asked == 0:
        correct = key[0]
    elif asked == 1:
        correct = key[1]
    else:
        correct = str(abs(key[2]))

    # Case-insensitive comparison
    if response.strip().lower() == correct.lower():

        quiz["completed"] = True
        user["coins"] = user.get("coins", 0) + 1

        update_file(USERS_URL, user_data, user_sha)

        await ctx.send(
            f"Correct!\n"
            f"You earned **1 WMGpeSO**.\n"
            f"You now have {user['coins']}."
        )

    else:
        await ctx.send(
            f"Incorrect.\n"
            f"The correct answer was **{correct}**."
        )

keep_alive()

BOT_TOKEN = os.environ["BOT_TOKEN"]
bot.run(BOT_TOKEN)
