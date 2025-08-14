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

# ---- Imports ----
import discord
from discord import app_commands
import os
import asyncio
from flask import Flask
from threading import Thread

# ---- Keep-alive web server ----
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ---- Bot Setup ----
intents = discord.Intents.default()
intents.guilds = True
intents.bans = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

@bot.event
async def on_ready():
    await tree.sync()  # Sync slash commands globally
    print(f"✅ Logged in as {bot.user}")
    print("✅ Slash commands synced")

# ---- /ping command ----
@tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! {round(bot.latency * 1000)}ms")

# ---- /unbanall command ----
@tree.command(name="unbanall", description="Unban all banned members and send them an invite")
@app_commands.checks.has_permissions(ban_members=True)
async def unbanall(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Fetching bans...")

    bans = await interaction.guild.bans()
    if not bans:
        await interaction.followup.send("✅ No banned members found.")
        return

    invite = await interaction.channel.create_invite(max_age=0, max_uses=0)
    await interaction.followup.send(f"🔄 Starting to unban {len(bans)} members...")

    for ban_entry in bans:
        user = ban_entry.user
        try:
            await interaction.guild.unban(user, reason="Mass unban command")
            try:
                await user.send(f"You have been unbanned from **{interaction.guild.name}**!\nHere’s your invite: {invite.url}")
            except:
                print(f"❌ Could not DM {user}")
            await asyncio.sleep(1)  # Avoid rate limit
        except Exception as e:
            print(f"Error unbanning {user}: {e}")

    await interaction.followup.send("✅ Finished unbanning all members.")

# ---- Start Bot ----
keep_alive()
bot.run(os.getenv("BOT_TOKEN"))
        
