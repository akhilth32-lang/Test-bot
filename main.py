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

@bot.tree.command(name="unban_all", description="Unban all banned members and send them an invite link")
async def unban_all(interaction: discord.Interaction):
    await interaction.response.send_message("⏳ Starting unban process... This may take a while.")

    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        await interaction.followup.send("❌ Bot is not in the server or GUILD_ID is wrong.")
        return

    # Create invite from the first text channel
    invite = None
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).create_instant_invite:
            invite = await channel.create_invite(max_age=86400, max_uses=0)
            break

    if not invite:
        await interaction.followup.send("❌ Could not create invite. Check bot permissions.")
        return

    message_text = (
        "⚠️ Our Discord server was hacked and everyone was banned.\n"
        "We have restored the server and unbanned you.\n"
        f"📨 Please rejoin using this invite: {invite.url}"
    )

    unbanned_count = 0
    failed_dm = 0

    try:
        async for ban_entry in guild.bans():
            user = ban_entry.user
            await guild.unban(user, reason="Mass unban")
            unbanned_count += 1
            try:
                await user.send(message_text)
            except:
                failed_dm += 1

        await interaction.followup.send(
            f"✅ Finished unbanning **{unbanned_count}** members.\n"
            f"📩 Sent invites to {unbanned_count - failed_dm} members.\n"
            f"🚫 Failed to DM {failed_dm} members (DMs closed)."
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

# Start keep_alive server
keep_alive()
bot.run(TOKEN)
