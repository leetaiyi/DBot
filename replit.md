# DBot — Discord Gacha Bot

A Discord bot that runs a gacha (loot pull) game for the WM Gacha community.

## Architecture

- **Language**: Python 3.12
- **Framework**: discord.py
- **Data storage**: GitHub repository (`prizes.json` in the same repo) via GitHub API
- **No frontend** — runs as a console workflow

## Key Files

- `gacha.py` — Main bot logic (commands, gacha mechanics, GitHub I/O)
- `prizes.json` — Local copy of gacha prizes (canonical version stored in GitHub)
- `WM Gacha/` — Image assets used in gacha embeds
- `pyproject.toml` — Python project dependencies

## Environment Secrets

- `BOT_TOKEN` — Discord bot token (Discord Developer Portal)
- `GITHUB_TOKEN` — GitHub personal access token with repo read/write access

## Bot Commands

- `!pull` — Pull from the gacha (costs 1 WMGpeSO coin, 10s cooldown)
- `!inventory` — View your collected prizes and coin balance
- `!addcoin @user [amount]` — Admin only: add coins to a user
- `!ping` — Health check

## Gacha Mechanics

- Users get 1 coin per day (daily reset)
- Pity system: guaranteed new item after 7 pulls
- Prizes have weighted rarity (weight 1 = ludicrously rare, weight 50 = common)
- Bot only responds in specific allowed Discord channels

## Workflow

- **Start application**: `python gacha.py` (console output, no port)
