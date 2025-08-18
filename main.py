# ---- Audioop bypass (must be first!) ----
import sys, types
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

# ========= IMPORTS ==========
import discord, os, aiohttp, asyncio
from discord.ext import commands
from discord import app_commands

# ========= ENV ==========
TOKEN = os.getenv("BOT_TOKEN")  # token from Render environment
BASE_URL = "https://api.clashk.ing"

# ========= BOT ==========
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ========= API CALLS ==========
async def search_player_by_name(name: str):
    url = f"{BASE_URL}/player/search/{name}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            return None

async def get_legends_data(tag: str):
    url = f"{BASE_URL}/player/{tag.replace('#','')}/legends"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            return None

# ========= AUTOCOMPLETE ==========
async def player_autocomplete(interaction: discord.Interaction, current: str):
    results = await search_player_by_name(current)
    choices = []
    if results and isinstance(results, list):
        for player in results[:10]:  # limit to 10 suggestions
            name = player.get("name")
            tag = player.get("tag")
            if name and tag:
                choices.append(app_commands.Choice(name=f"{name} | {tag}", value=tag))
    return choices

# ========= COMMAND ==========
@bot.tree.command(name="base", description="Get VIP base details for a player")
@app_commands.describe(count="Base number", player="Search by IGN or tag")
@app_commands.autocomplete(player=player_autocomplete)
async def base(interaction: discord.Interaction, count: int, player: str):
    await interaction.response.defer()

    # If player is a tag → fetch directly
    if player.startswith("#") or player[0].isalnum():
        data = await get_legends_data(player)
    else:
        # Fallback (should not hit because autocomplete handles it)
        results = await search_player_by_name(player)
        if not results or not isinstance(results, list):
            await interaction.followup.send("⚠️ No players found.")
            return
        tag = results[0]["tag"]
        data = await get_legends_data(tag)

    if not data:
        await interaction.followup.send("⚠️ Could not fetch player details.")
        return

    player_name = data.get("name", "Unknown")
    player_tag = data.get("tag", "N/A")
    eod_trophies = data.get("start", "N/A")

    # Format message
    formatted = f"""
** VIP base `{count}`**
╰┈➤
Recent base of **"{player_name}"**
> EOD `{eod_trophies}` 🏆 
> Original traps
> Player Tag : `{player_tag}`

**Clan Castle**
> 1x Electro Titan, 1x Dragon and Archers!
OR
> 1x S drag + Archers!
"""

    await interaction.followup.send(formatted)

# ========= RUN ==========
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ Sync error: {e}")

bot.run(TOKEN)
