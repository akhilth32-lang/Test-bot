import discord
from discord.ext import commands
import os
import asyncio
from flask import Flask
from threading import Thread
import sys, types

# Audioop bypass
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

# Flask keep-alive server
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Bot setup
intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.message_content = True
intents.bans = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# Ping command
@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! {round(bot.latency * 1000)}ms")

# Unban all command
@bot.command()
@commands.has_permissions(ban_members=True)
async def unbanall(ctx):
    bans = await ctx.guild.bans()
    if not bans:
        await ctx.send("✅ No banned members found.")
        return

    invite = await ctx.channel.create_invite(max_age=0, max_uses=0)
    await ctx.send(f"🔄 Starting to unban {len(bans)} members...")

    for ban_entry in bans:
        user = ban_entry.user
        try:
            await ctx.guild.unban(user, reason="Mass unban command")
            try:
                await user.send(f"You have been unbanned from **{ctx.guild.name}**!\nHere’s your invite: {invite.url}")
            except:
                print(f"❌ Could not DM {user}")
            await asyncio.sleep(1)  # Avoid rate limit
        except Exception as e:
            print(f"Error unbanning {user}: {e}")

    await ctx.send("✅ Finished unbanning all members.")

keep_alive()
bot.run(os.getenv("BOT_TOKEN"))
