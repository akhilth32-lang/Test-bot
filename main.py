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

import os
import discord
from discord.ext import commands
from discord import app_commands
from keep_alive import keep_alive

# ================== CONFIG ==================
TOKEN = os.getenv("BOT_TOKEN")  # Render environment variable
GUILD_ID = 1352037302590902462  # Your server ID
# =============================================

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"✅ Synced {len(synced)} command(s).")
    except Exception as e:
        print(f"❌ Sync failed: {e}")

@bot.tree.command(name="unban_all", description="Unban all banned members and send them an invite")
async def unban_all(interaction: discord.Interaction):
    await interaction.response.send_message("⏳ Starting unban process... Please wait.", ephemeral=True)
    
    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        await interaction.followup.send("❌ Bot is not in the server or GUILD_ID is wrong.", ephemeral=True)
        return
    
    # Create an invite
    invite = await guild.text_channels[0].create_invite(max_age=86400, max_uses=0)
    message_text = f"Someone hacked the server and banned everyone 😢\nPlease join again using this link: {invite.url}"

    unbanned_count = 0
    try:
        async for ban_entry in guild.bans():
            user = ban_entry.user
            await guild.unban(user, reason="Mass unban requested")
            unbanned_count += 1
            try:
                await user.send(message_text)
            except:
                pass  # ignore if DMs are closed

        await interaction.followup.send(f"✅ Finished unbanning {unbanned_count} members.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

# Start keep_alive server
keep_alive()
bot.run(TOKEN)
