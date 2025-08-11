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
MONGO_URI = os.getenv("MONGO_URI")           # original DB (left untouched)
NEW_MONGO_URI = os.getenv("NEW_MONGO_URI")   # NEW DB to use if provided
NEW_DB_NAME = os.getenv("NEW_DB_NAME", "coc_bot_v2")

PROXY_URL = os.getenv("PROXY_URL", "https://clash-of-clans-api-4bi0.onrender.com")

LEADERBOARD_PAGE_SIZE = int(os.getenv("LEADERBOARD_PAGE_SIZE", "10"))

EMOJI_TROPHY = "<:trophy:1400826511799484476>"
EMOJI_OFFENSE = "<:Offence:1400826628099014676>"
EMOJI_DEFENSE = "<:emoji_9:1252010455694835743>"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
# PART 1/5 END
# ======================= MONGO INIT =======================
# Use NEW_MONGO_URI if present (so your old DB remains untouched)
if NEW_MONGO_URI:
    mongo_client = MongoClient(NEW_MONGO_URI)
    db = mongo_client[NEW_DB_NAME]
    print("🔁 Using NEW_MONGO_URI and DB:", NEW_DB_NAME)
else:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client["coc_bot"]
    print("⚠️ NEW_MONGO_URI not set. Using original DB 'coc_bot'.")

players_col = db["players"]
backup_col = db["backup_players"]
daily_stats_col = db["daily_stats"]
players_col.create_index([("trophies", -1)])

# ======================= DB HELPERS (unchanged semantics) =======================
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

# ======================= SEASON INFO (robust) =======================
def _parse_date_str(s):
    if not s:
        return None
    # accept formats: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, with optional Z
    try:
        s2 = s.strip()
        if s2.endswith("Z"):
            s2 = s2[:-1]
        # if no time, fromisoformat still works
        return datetime.fromisoformat(s2).date()
    except Exception:
        # last fallback try date only
        try:
            return datetime.strptime(s.split("T")[0], "%Y-%m-%d").date()
        except Exception:
            return None

def fetch_season_info():
    # Try a few endpoints on proxy that may contain season info. This is best-effort.
    endpoints = ["/season", "/seasons/legend", "/legend/season", "/seasons/current"]
    for ep in endpoints:
        try:
            url = PROXY_URL.rstrip("/") + ep
            r = requests.get(url, timeout=6)
            if r.status_code != 200:
                continue
            data = r.json()
            # try common shapes
            # shape 1: {"start":"2025-08-01","end":"2025-08-28"}
            if isinstance(data, dict) and "start" in data and "end" in data:
                return {"start": _parse_date_str(data["start"]), "end": _parse_date_str(data["end"])}
            # shape 2: {"season":{"start":"...","end":"..."}}
            if isinstance(data, dict) and "season" in data and isinstance(data["season"], dict):
                return {"start": _parse_date_str(data["season"].get("start")), "end": _parse_date_str(data["season"].get("end"))}
            # shape 3: array of seasons -> pick current (first) element
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and "start" in data[0] and "end" in data[0]:
                return {"start": _parse_date_str(data[0]["start"]), "end": _parse_date_str(data[0]["end"])}
        except Exception:
            continue
    return None

def compute_season_day():
    season = fetch_season_info()
    if season and season.get("start") and season.get("end"):
        start = season["start"]
        end = season["end"]
        try:
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
    # fallback: use env SEASON_START_DATE or assume 28 days
    fallback_len = int(os.getenv("FALLBACK_SEASON_LENGTH", "28"))
    start_str = os.getenv("SEASON_START_DATE")
    if start_str:
        s = _parse_date_str(start_str)
        if s:
            today_ist = (datetime.utcnow() + timedelta(hours=5, minutes=30)).date()
            day_num = (today_ist - s).days + 1
            if day_num < 1: day_num = 1
            if day_num > fallback_len: day_num = fallback_len
            return day_num, fallback_len
    return 1, fallback_len
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
            print(f"❌ Error updating {player.get('player_tag','<unknown>')}: {e}")
    print("✅ Update finished!")

@tasks.loop(minutes=1)
async def backup_leaderboard():
    global last_backup_date
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)  # IST
    if now.hour == 10 and now.minute == 25 and last_backup_date != now.date():
        players = list(players_col.find({}))
        if players:
            try:
                backup_col.delete_many({})
                cleaned = []
                for p in players:
                    p_copy = p.copy()
                    p_copy.pop("_id", None)
                    cleaned.append(p_copy)
                if cleaned:
                    backup_col.insert_many(cleaned)

                season_day, season_len = compute_season_day()
                stats_doc = {
                    "date": now.date().isoformat(),
                    "season_day": season_day,
                    "season_len": season_len,
                    "players": []
                }

                for p in players:
                    tag = p.get("player_tag")
                    start_t = p.get("prev_trophies", p.get("trophies", 0))
                    end_t = p.get("trophies", 0)
                    off_attacks = p.get("offense_attacks", 0)
                    off_trophies = p.get("offense_trophies", 0)
                    def_defenses = p.get("defense_defenses", 0)
                    def_trophies = p.get("defense_trophies", 0)

                    try:
                        t_enc = tag if tag.startswith("#") else f"#{tag}"
                        t_enc = t_enc.replace("#", "%23")
                        url = f"{PROXY_URL}/player/{t_enc}"
                        r = requests.get(url, timeout=8)
                        if r.status_code == 200:
                            pdata = r.json()
                            a_log = pdata.get("attackLog", [])
                            d_log = pdata.get("defenseLog", [])
                            total_off_t = 0
                            total_off_count = 0
                            for a in a_log:
                                tc = a.get("trophyChange")
                                if tc is None:
                                    continue
                                total_off_t += max(0, tc)
                                total_off_count += 1
                            total_def_t = 0
                            total_def_count = 0
                            for d in d_log:
                                tc = d.get("trophyChange")
                                if tc is None:
                                    continue
                                total_def_t += abs(min(0, tc))
                                total_def_count += 1
                            if total_off_count > 0:
                                off_attacks = total_off_count
                                off_trophies = total_off_t
                            if total_def_count > 0:
                                def_defenses = total_def_count
                                def_trophies = total_def_t
                    except Exception:
                        pass

                    stats_doc["players"].append({
                        "player_tag": tag,
                        "name": p.get("name"),
                        "start_trophies": start_t,
                        "end_trophies": end_t,
                        "delta": end_t - start_t,
                        "offense_trophies": off_trophies,
                        "offense_attacks": off_attacks,
                        "defense_trophies": def_trophies,
                        "defense_defenses": def_defenses
                    })

                daily_stats_col.insert_one(stats_doc)
                last_backup_date = now.date()
                print(f"💾 Backup & daily_stats saved with {len(stats_doc['players'])} players (10:25 AM IST)")
            except Exception as e:
                print("❌ Error during backup_leaderboard:", e, traceback.format_exc())

@tasks.loop(minutes=1)
async def reset_offense_defense():
    global last_reset_date
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)  # IST
    if now.hour == 10 and now.minute == 30 and last_reset_date != now.date():
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
        # ======================= UI LEADERBOARD =======================
class PlayerSelect(ui.Select):
    def __init__(self, players):
        options = []
        for p in players:
            label = f"{p.get('name','Unknown')}"
            value = p.get('player_tag')
            if len(label) > 80:
                label = label[:77] + "..."
            options.append(discord.SelectOption(label=label, value=value))
        super().__init__(placeholder="Select player to view today's stats...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        tag = self.values[0]
        tag_upper = tag.upper()

        # Fetch latest daily_stats document
        last_doc = daily_stats_col.find_one(sort=[("date", -1)])
        player_doc = None
        if last_doc:
            player_doc = next((p for p in last_doc.get("players", []) if (p.get("player_tag","").upper() == tag_upper)), None)

        # Fallback to live player data or zeros
        if not player_doc:
            p = players_col.find_one({"player_tag": tag})
            if p:
                player_doc = {
                    "player_tag": p.get("player_tag"),
                    "name": p.get("name"),
                    "start_trophies": p.get("prev_trophies", p.get("trophies", 0)),
                    "end_trophies": p.get("trophies", 0),
                    "delta": p.get("trophies", 0) - p.get("prev_trophies", p.get("trophies", 0)),
                    "offense_trophies": p.get("offense_trophies", 0),
                    "offense_attacks": p.get("offense_attacks", 0),
                    "defense_trophies": p.get("defense_trophies", 0),
                    "defense_defenses": p.get("defense_defenses", 0),
                }
            else:
                player_doc = {
                    "player_tag": tag,
                    "name": "Unknown",
                    "start_trophies": 0,
                    "end_trophies": 0,
                    "delta": 0,
                    "offense_trophies": 0,
                    "offense_attacks": 0,
                    "defense_trophies": 0,
                    "defense_defenses": 0,
                }

        # Format superscript numbers helper
        def format_count(n):
            sup_map = {"0":"⁰","1":"¹","2":"²","3":"³","4":"⁴","5":"⁵","6":"⁶","7":"⁷","8":"⁸","9":"⁹"}
            s = str(n)
            return "".join(sup_map.get(ch, ch) for ch in s)

        header = f"{player_doc.get('name')} | #{player_doc.get('player_tag')}\n\n"
        overview = (
            "**Overview**\n"
            f"- Start Trophies: {player_doc.get('start_trophies', 0)}\n"
            f"- End Trophies: {player_doc.get('end_trophies', 0)}\n"
            f"- Delta Trophies: {player_doc.get('delta', 0)}\n"
        )

        attacks_lines = []
        defenses_lines = []

        try:
            docs = list(daily_stats_col.find({"players.player_tag": {"$regex": f"^{tag_upper}$", "$options": "i"}}).sort("date", -1).limit(7))
            if docs:
                docs = list(reversed(docs))  # oldest -> newest
                for d in docs:
                    p = next((x for x in d.get("players", []) if (x.get("player_tag","").upper() == tag_upper)), None)
                    if p:
                        atk_t = p.get("offense_trophies", 0)
                        atk_n = p.get("offense_attacks", 0)
                        def_t = p.get("defense_trophies", 0)
                        def_n = p.get("defense_defenses", 0)
                        atk_sup = format_count(atk_n)
                        def_sup = format_count(def_n)
                        attacks_lines.append(f" {atk_t}+{atk_sup}")
                        defenses_lines.append(f" {def_t}-{def_sup}")
        except Exception:
            # On error or no data, fallback to single row
            attacks_lines = [f" {player_doc.get('offense_trophies', 0)}+{format_count(player_doc.get('offense_attacks', 0))}"]
            defenses_lines = [f" {player_doc.get('defense_trophies', 0)}-{format_count(player_doc.get('defense_defenses', 0))}"]

        if not attacks_lines:
            attacks_lines = [f" {player_doc.get('offense_trophies', 0)}+{format_count(player_doc.get('offense_attacks', 0))}"]
        if not defenses_lines:
            defenses_lines = [f" {player_doc.get('defense_trophies', 0)}-{format_count(player_doc.get('defense_defenses', 0))}"]

        code_lines = []
        max_rows = max(len(attacks_lines), len(defenses_lines))
        for i in range(max_rows):
            a = attacks_lines[i] if i < len(attacks_lines) else " 0"
            d = defenses_lines[i] if i < len(defenses_lines) else " 0"
            code_lines.append(f"{a:<8}   {d}")

        code_block = "```Attacks   Defenses\n" + "\n".join(code_lines) + "\n```"

        content = header + overview + code_block
        embed = discord.Embed(title=f"{player_doc.get('name')} | #{player_doc.get('player_tag')}", description=overview)
        # Send ephemeral response with content formatted as requested
        await interaction.response.send_message(content, ephemeral=True)


class LeaderboardView(ui.View):
    def __init__(self, players, color, name, page=0):
        super().__init__(timeout=None)
        self.players = players
        self.color = color
        self.name = name
        self.page = page

        try:
            self.add_item(PlayerSelect(players))
        except Exception as e:
            print("⚠️ Could not add PlayerSelect:", e)

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

    @ui.button(label="⬅️", style=discord.ButtonStyle.secondary, row=0)
    async def prev_page(self, interaction, button):
        if self.page > 0:
            self.page -= 1
            await self.update_message(interaction)

    @ui.button(label="🔄", style=discord.ButtonStyle.primary, row=0)
    async def refresh(self, interaction, button):
        await self.update_message(interaction)

    @ui.button(label="➡️", style=discord.ButtonStyle.secondary, row=0)
    async def next_page(self, interaction, button):
        if (self.page + 1) * LEADERBOARD_PAGE_SIZE < len(self.players):
            self.page += 1
            await self.update_message(interaction)

# ======================= Discord Slash Commands (unchanged) =======================
# (Your existing /link, /unlink, /remove, /leaderboard, /player-history commands remain same here)
# ======================= BOT STARTUP (unchanged) =======================
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
