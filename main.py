# PART 1/4
import sys
import types

# ✅ Bypass for audioop crashes (keeps your original bypass)
sys.modules['audioop'] = types.ModuleType('audioop')
sys.modules['audioop'].mul = lambda *args, **kwargs: None
sys.modules['audioop'].add = lambda *args, **kwargs: None
sys.modules['audioop'].getsample = lambda *args, **kwargs: 0
sys.modules['audioop'].max = lambda *args, **kwargs: 0
sys.modules['audioop'].minmax = lambda *args, **kwargs: (0, 0)
sys.modules['audioop'].avg = lambda *args, **kwargs: 0
sys.modules['audioop'].avgpp = lambda *args, **kwargs: 0
sys.modules['audioop'].rms = lambda *args, **kwargs: 0
sys.modules['audioop'].cross = lambda *args, **kwargs: 0

import discord, asyncio, requests, os, traceback, io
from discord.ext import commands, tasks
from discord import app_commands, ui, File
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from keep_alive import keep_alive  # ✅ Using separate keep_alive file
import matplotlib
matplotlib.use('Agg')  # use non-interactive backend for servers
import matplotlib.pyplot as plt

keep_alive()  # ✅ Start Flask keepalive server

# ======================= CONFIG =======================
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")            # existing DB (do not touch)
NEW_MONGO_URI = os.getenv("NEW_MONGO_URI")    # new DB (the one we'll use if present)
NEW_DB_NAME = os.getenv("NEW_DB_NAME", "coc_bot_v2")  # default new DB name

PROXY_URL = "https://clash-of-clans-api-4bi0.onrender.com"

LEADERBOARD_PAGE_SIZE = 10
EMOJI_TROPHY = "<:trophy:1400826511799484476>"
EMOJI_OFFENSE = "<:Offence:1400826628099014676>"
EMOJI_DEFENSE = "<:emoji_9:1252010455694835743>"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
# PART 2/4
# ======================= MONGO INIT =======================
# Use NEW_MONGO_URI if present (so we don't touch the old DB unless you want to)
if NEW_MONGO_URI:
    mongo_client = MongoClient(NEW_MONGO_URI)
    print("🔁 Using NEW_MONGO_URI (isolated new database).")
else:
    mongo_client = MongoClient(MONGO_URI)
    print("⚠️ NEW_MONGO_URI not set: falling back to MONGO_URI (original DB).")

db = mongo_client[NEW_DB_NAME if NEW_MONGO_URI else "coc_bot"]
players_col = db["players"]
backup_col = db["backup_players"]
daily_stats_col = db["daily_stats"]
players_col.create_index([("trophies", -1)])

# ======================= DB HELPERS =======================
def add_or_update_player(discord_id, tag, data):
    update = {
        "discord_id": discord_id,
        "player_tag": tag,
        "name": data["name"],
        "trophies": data["trophies"],
        "rank": data.get("rank", 0),
        "prev_trophies": data.get("prev_trophies", data["trophies"]),
        "prev_rank": data.get("prev_rank", data["rank"]),
        "attacks": data.get("attacks", 0),
        "defenses": data.get("defenses", 0),
        "offense_trophies": data.get("offense_trophies", 0),
        "offense_attacks": data.get("offense_attacks", 0),
        "defense_trophies": data.get("defense_trophies", 0),
        "defense_defenses": data.get("defense_defenses", 0),
        "last_reset": data.get("last_reset", datetime.now().strftime("%Y-%m-%d"))
    }
    players_col.update_one({"player_tag": tag}, {"$set": update}, upsert=True)
    print(f"✅ Player updated/added: {data['name']} ({tag})")

def get_all_players():
    return list(players_col.find().sort("trophies", -1))

def remove_player(discord_id, tag=None):
    if tag:
        result = players_col.delete_one({"discord_id": discord_id, "player_tag": tag.replace("#", "")})
        print(f"🔁 Removed one: matched={result.deleted_count}")
    else:
        result = players_col.delete_many({"discord_id": discord_id})
        print(f"🔁 Removed all: matched={result.deleted_count}")

# ======================= SAFE API CALL =======================
def fetch_player_data(tag: str):
    tag_encoded = tag if tag.startswith("#") else f"#{tag}"
    tag_encoded = tag_encoded.replace("#", "%23")
    url = f"{PROXY_URL}/player/{tag_encoded}"

    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            print(f"❌ HTTP {r.status_code} for {tag} -> {r.text}")
            return None

        data = r.json()
        if not data or "name" not in data or "trophies" not in data:
            print(f"⚠️ Incomplete data for {tag} -> {data}")
            return None

        return {
            "name": data["name"],
            "trophies": data["trophies"],
            "rank": data.get("rank", 0),
            "attacks": len(data.get("attackLog", [])),
            "defenses": len(data.get("defenseLog", []))
        }

    except Exception as e:
        print(f"❌ Exception for {tag}: {e}")
        return None

async def async_fetch_player_data(tag):
    return await asyncio.to_thread(fetch_player_data, tag)

# ======================= SEASON INFO HELPERS =======================
# Tries to fetch season start/end info from proxy (if supported). Fails safely.
def fetch_season_info():
    try:
        url = f"{PROXY_URL}/season"  # best-effort endpoint; proxy should return season metadata if available
        r = requests.get(url, timeout=8)
        if r.status_code != 200:
            return None
        data = r.json()
        # expected structure: {"start": "2025-08-01", "end": "2025-08-28"} - this is best-effort
        return data
    except Exception:
        return None

def compute_season_day():
    season = fetch_season_info()
    if season and "start" in season and "end" in season:
        try:
            start = datetime.fromisoformat(season["start"]).date()
            end = datetime.fromisoformat(season["end"]).date()
            total = (end - start).days + 1
            today_ist = (datetime.utcnow() + timedelta(hours=5, minutes=30)).date()
            day_num = (today_ist - start).days + 1
            if day_num < 1:
                day_num = 1
            if day_num > total:
                day_num = total
            return day_num, total
        except Exception:
            pass
    # Fallback: assume 28-day season and use SEASON_START_DATE if provided
    fallback_len = int(os.getenv("FALLBACK_SEASON_LENGTH", "28"))
    start_str = os.getenv("SEASON_START_DATE")  # optional "YYYY-MM-DD"
    if start_str:
        try:
            start = datetime.fromisoformat(start_str).date()
            today_ist = (datetime.utcnow() + timedelta(hours=5, minutes=30)).date()
            day_num = (today_ist - start).days + 1
            if day_num < 1:
                day_num = 1
            if day_num > fallback_len:
                day_num = fallback_len
            return day_num, fallback_len
        except Exception:
            pass
    # final fallback
    return 1, fallback_len
  # PART 3/4
# ======================= BACKGROUND TASKS =======================
last_reset_date = None
last_backup_date = None

@tasks.loop(minutes=1)
async def update_players_data():
    players = get_all_players()
    print(f"\n⏳ Background update: {len(players)} players")
    for player in players:
        try:
            discord_id = player["discord_id"]
            tag = player["player_tag"]

            trophies = player["trophies"]
            rank = player.get("rank", 0)
            off_t = player.get("offense_trophies", 0)
            off_a = player.get("offense_attacks", 0)
            def_t = player.get("defense_trophies", 0)
            def_d = player.get("defense_defenses", 0)

            data = await async_fetch_player_data(tag)
            if data:
                delta = data["trophies"] - trophies
                if delta > 0:
                    off_t += delta
                    off_a += 1
                elif delta < 0:
                    def_t += abs(delta)
                    def_d += 1

                data.update({
                    "prev_trophies": trophies,
                    "prev_rank": rank,
                    "offense_trophies": off_t,
                    "offense_attacks": off_a,
                    "defense_trophies": def_t,
                    "defense_defenses": def_d,
                    "last_reset": datetime.now().strftime("%Y-%m-%d")
                })
                add_or_update_player(discord_id, tag, data)
            else:
                print(f"❌ Failed: {tag}")
        except Exception as e:
            print(f"❌ Error updating {player.get('player_tag', '<unknown>')}: {e}")
    print("✅ Update finished!")

@tasks.loop(minutes=1)
async def reset_offense_defense():
    global last_reset_date
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)  # IST
    if now.hour == 10 and now.minute == 30 and last_reset_date != now.date():
        # Reset daily counters (same behavior)
        players_col.update_many({}, {
            "$set": {
                "offense_trophies": 0,
                "offense_attacks": 0,
                "defense_trophies": 0,
                "defense_defenses": 0
            }
        })
        last_reset_date = now.date()
        print("🔁 Daily offense/defense reset done (10:30 AM IST)")

@tasks.loop(minutes=1)
async def backup_leaderboard():
    """
    At 10:25 AM IST: take snapshot of players, create daily_stats doc and backup players collection.
    This runs every minute but triggers only at 10:25.
    """
    global last_backup_date
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)  # IST
    if now.hour == 10 and now.minute == 25 and last_backup_date != now.date():
        players = list(players_col.find({}))
        if players:
            # Save entire players snapshot into backup collection (clear and insert)
            try:
                backup_col.delete_many({})
                # remove Mongo ObjectIds in snapshots to avoid serialize issues
                cleaned = []
                for p in players:
                    p_copy = p.copy()
                    p_copy.pop("_id", None)
                    cleaned.append(p_copy)
                if cleaned:
                    backup_col.insert_many(cleaned)

                # Create structured daily_stats document for this day
                season_day, season_len = compute_season_day()
                stats_doc = {
                    "date": now.date().isoformat(),
                    "season_day": season_day,
                    "season_len": season_len,
                    "players": []
                }
                for p in players:
                    start_t = p.get("prev_trophies", p.get("trophies", 0))
                    end_t = p.get("trophies", 0)
                    stats_doc["players"].append({
                        "player_tag": p.get("player_tag"),
                        "name": p.get("name"),
                        "start_trophies": start_t,
                        "end_trophies": end_t,
                        "delta": end_t - start_t,
                        "offense_trophies": p.get("offense_trophies", 0),
                        "offense_attacks": p.get("offense_attacks", 0),
                        "defense_trophies": p.get("defense_trophies", 0),
                        "defense_defenses": p.get("defense_defenses", 0)
                    })

                # Insert into daily_stats collection
                daily_stats_col.insert_one(stats_doc)
                last_backup_date = now.date()
                print(f"💾 Backup & daily_stats saved with {len(stats_doc['players'])} players (10:25 AM IST)")

            except Exception as e:
                print(f"❌ Error during backup_leaderboard: {e}")
              # PART 4/4
# ======================= UI LEADERBOARD =======================
class PlayerSelect(ui.Select):
    def __init__(self, players):
        options = []
        for p in players:
            # Display name as "Name | #TAG" (short)
            label = f"{p.get('name', 'Unknown')}"
            value = p.get('player_tag')
            # limit label length
            if len(label) > 80:
                label = label[:77] + "..."
            options.append(discord.SelectOption(label=label, value=value))

        super().__init__(placeholder="Select player to view today's saved stats...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        tag = self.values[0]
        # Fetch latest daily_stats document
        last_doc = daily_stats_col.find_one(sort=[("date", -1)])
        if not last_doc:
            await interaction.response.send_message("❌ No daily stats available yet.", ephemeral=True)
            return

        player_doc = next((p for p in last_doc.get("players", []) if p.get("player_tag", "").upper() == tag.upper()), None)
        if not player_doc:
            await interaction.response.send_message("❌ Player not found in latest daily stats.", ephemeral=True)
            return

        # Format message as requested
        name_line = f"{player_doc.get('name')} | #{player_doc.get('player_tag')}"
        overview = (
            f"**Overview**\n"
            f"- Start Trophies: {player_doc.get('start_trophies')}\n"
            f"- End Trophies: {player_doc.get('end_trophies')}\n"
            f"- Delta Trophies: {player_doc.get('delta')}\n"
        )

        # Construct small attacks/defenses block (summary)
        attacks = player_doc.get("offense_attacks", 0)
        defenses = player_doc.get("defense_defenses", 0)
        attacks_troph = player_doc.get("offense_trophies", 0)
        defenses_troph = player_doc.get("defense_trophies", 0)

        attacks_block = f"Attacks: {attacks_troph} ({attacks} attacks)"
        defenses_block = f"Defenses: -{defenses_troph} ({defenses} defenses)"

        embed = discord.Embed(title=name_line, description=f"{overview}\n```{attacks_block}\n{defenses_block}```")
        await interaction.response.send_message(embed=embed, ephemeral=True)

class LeaderboardView(ui.View):
    def __init__(self, players, color, name, page=0):
        super().__init__(timeout=None)
        self.players = players
        self.color = color
        self.name = name
        self.page = page

        # Add the player select dropdown (list all registered players)
        try:
            self.add_item(PlayerSelect(players))
        except Exception as e:
            print(f"⚠️ Could not add PlayerSelect: {e}")

    def get_embed(self):
        start = self.page * LEADERBOARD_PAGE_SIZE
        end = start + LEADERBOARD_PAGE_SIZE
        embed = discord.Embed(title=self.name, color=self.color)

        now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
        season_day, season_len = compute_season_day()
        embed.set_footer(text=f"Last refreshed: {now_ist.strftime('%d-%m-%Y %I:%M %p')} | Season Day: {season_day}/{season_len}")

        for i, p in enumerate(self.players[start:end], start=start + 1):
            embed.add_field(
                name=f"{i}. {p['name']} (#{p['player_tag']})",
                value=f"{EMOJI_TROPHY} {p['trophies']} | {EMOJI_OFFENSE} +{p.get('offense_trophies', 0)}/{p.get('offense_attacks', 0)} | {EMOJI_DEFENSE} -{p.get('defense_trophies', 0)}/{p.get('defense_defenses', 0)}\n\u200b",
                inline=False
            )
        return embed

    async def update_message(self, interaction):
        await interaction.response.defer()
        self.players = get_all_players()
        await interaction.edit_original_response(embed=self.get_embed(), view=self)

    @ui.button(label="⬅️ Previous", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction, button):
        if self.page > 0:
            self.page -= 1
            await self.update_message(interaction)

    @ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction, button):
        if (self.page + 1) * LEADERBOARD_PAGE_SIZE < len(self.players):
            self.page += 1
            await self.update_message(interaction)

    @ui.button(label="🔄 Refresh", style=discord.ButtonStyle.primary)
    async def refresh(self, interaction, button):
        await self.update_message(interaction)

# ======================= DISCORD COMMANDS =======================
@bot.tree.command(name="link")
@app_commands.describe(player_tag="Your Clash of Clans player tag (e.g. #8YJ98LV2C)")
async def link(interaction: discord.Interaction, player_tag: str):
    await interaction.response.defer(thinking=True)
    tag = player_tag.replace("#", "").upper()
    data = await async_fetch_player_data(tag)
    if data:
        add_or_update_player(interaction.user.id, tag, data)
        await interaction.followup.send(f"✅ Linked **{data['name']}** (`{player_tag}`) to your account.")
    else:
        await interaction.followup.send("❌ Failed to fetch player data. Please check the tag and try again.")

@bot.tree.command(name="unlink")
@app_commands.describe(player_tag="Optional: tag to unlink (remove all if left blank)")
async def unlink(interaction: discord.Interaction, player_tag: str = None):
    await interaction.response.defer()
    tag = player_tag.replace("#", "").upper() if player_tag else None
    remove_player(interaction.user.id, tag)
    await interaction.followup.send("✅ Account unlinked.", ephemeral=True)

@bot.tree.command(name="remove")
@app_commands.describe(player_tag="Tag to forcibly remove from the leaderboard")
async def remove(interaction: discord.Interaction, player_tag: str):
    await interaction.response.defer()
    tag = player_tag.replace("#", "").upper()
    result = players_col.delete_one({"player_tag": tag})
    if result.deleted_count:
        await interaction.followup.send(f"✅ Removed player `{tag}` from leaderboard.")
    else:
        await interaction.followup.send("❌ Player not found.")

@bot.tree.command(name="leaderboard")
@app_commands.describe(
    color="Embed color (default blue)",
    name="Leaderboard title",
    force_reset="Set to True to reset offense/defense stats before showing leaderboard"
)
async def leaderboard(
    interaction: discord.Interaction,
    color: str = "0x3498db",
    name: str = "🏆 Leaderboard",
    force_reset: bool = False
):
    await interaction.response.defer(thinking=True)

    # ✅ Force reset if requested
    if force_reset:
        players_col.update_many({}, {
            "$set": {
                "offense_trophies": 0,
                "offense_attacks": 0,
                "defense_trophies": 0,
                "defense_defenses": 0
            }
        })
        print(f"⚡ Force reset done by {interaction.user} at {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")

    try:
        color = int(color, 16)
    except:
        color = 0x3498db

    players = get_all_players()
    view = LeaderboardView(players, color, name)
    await interaction.followup.send(embed=view.get_embed(), view=view)

# ======================= /player-history command (new) =======================
@bot.tree.command(name="player-history")
@app_commands.describe(player_tag="Player tag (e.g. #R0VCQPCR)", days="Number of past days to show (default 28)")
async def player_history(interaction: discord.Interaction, player_tag: str, days: int = 28):
    await interaction.response.defer(thinking=True)

    tag = player_tag.replace("#", "").upper()
    # Fetch last N days of daily_stats
    docs = list(daily_stats_col.find({"players.player_tag": {"$regex": f"^{tag}$", "$options": "i"}}).sort("date", -1).limit(days))
    if not docs:
        await interaction.followup.send("❌ No history available for this player yet. Wait until a daily backup runs at 10:25 AM IST.", ephemeral=True)
        return

    # Collect dates and end_trophies (most recent first -> reverse later)
    dates = []
    end_trophies = []
    for d in reversed(docs):  # oldest->newest
        dates.append(d.get("date"))
        p = next((p for p in d.get("players", []) if p.get("player_tag", "").upper() == tag.upper()), None)
        if p:
            end_trophies.append(p.get("end_trophies", 0))
        else:
            end_trophies.append(None)

    # Fallback if any None: replace with previous known or 0
    for i in range(len(end_trophies)):
        if end_trophies[i] is None:
            end_trophies[i] = end_trophies[i-1] if i > 0 else 0

    # Make chart
    try:
        plt.figure(figsize=(8,4))
        plt.plot(dates, end_trophies, marker='o')
        plt.title(f"Trophies over last {len(dates)} days - {tag}")
        plt.xlabel("Date")
        plt.ylabel("End-of-day Trophies")
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()

        # Get player name from most recent doc
        last_doc = docs[0]
        last_player = next((p for p in last_doc.get("players", []) if p.get("player_tag", "").upper() == tag.upper()), None)
        player_name = last_player.get("name") if last_player else tag

        # Small summary
        total_delta = 0
        total_off_t = 0
        total_def_t = 0
        for d in docs:
            p = next((p for p in d.get("players", []) if p.get("player_tag", "").upper() == tag.upper()), None)
            if p:
                total_delta += p.get("delta", 0)
                total_off_t += p.get("offense_trophies", 0)
                total_def_t += p.get("defense_trophies", 0)

        embed = discord.Embed(title=f"{player_name} | #{tag}", description=f"Showing last {len(dates)} days")
        embed.add_field(name="Summary", value=f"Delta (sum): {total_delta}\nOffense trophies (sum): {total_off_t}\nDefense trophies (sum): {total_def_t}", inline=False)

        file = File(fp=buf, filename="history.png")
        await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        print(f"❌ Error generating chart: {e}")
        await interaction.followup.send("❌ Error generating chart. Check server logs.", ephemeral=True)

# ======================= BOT STARTUP =======================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")
    update_players_data.start()
    reset_offense_defense.start()
    backup_leaderboard.start()

try:
    bot.run(TOKEN, reconnect=True)
except Exception as e:
    print(f"❌ Bot failed to run: {e}")
