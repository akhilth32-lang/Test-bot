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

import discord
from discord import app_commands
from discord.ext import commands
import os
from keep_alive import keep_alive

TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.default()
intents.bans = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ Sync failed: {e}")

@bot.tree.command(name="unban_all", description="Unban all banned members and DM them an invite link. Optionally log failed DMs.")
@app_commands.describe(log_channel_id="Optional channel ID to log members who couldn't be DMed")
async def unban_all(interaction: discord.Interaction, log_channel_id: str = None):
    await interaction.response.send_message("⏳ Starting unban process... Please wait.", ephemeral=False)

    guild = interaction.guild
    failed_dms = []

    # Create invite link (permanent, unlimited uses)
    invite = await interaction.channel.create_invite(max_age=0, max_uses=0)
    message_text = (
        f"Hello! 👋\n\n"
        f"Our server was hacked and many members were banned by mistake.\n"
        f"Please join us again using this link: {invite.url}\n\n"
        f"We're sorry for the inconvenience ❤️"
    )

    async for ban_entry in guild.bans():
        user = ban_entry.user
        try:
            await guild.unban(user, reason="Mass unban command")
            try:
                await user.send(message_text)
            except:
                failed_dms.append(f"{user} ({user.id})")
        except Exception as e:
            print(f"❌ Failed to unban {user}: {e}")

    # Log failed DMs if channel ID provided
    if log_channel_id and failed_dms:
        try:
            log_channel = guild.get_channel(int(log_channel_id))
            if log_channel:
                chunks = [failed_dms[i:i+40] for i in range(0, len(failed_dms), 40)]
                for chunk in chunks:
                    await log_channel.send(
                        "**📜 Failed to DM these members:**\n" +
                        "\n".join(chunk)
                    )
        except Exception as e:
            print(f"❌ Failed to log in channel: {e}")

    await interaction.followup.send(
        f"✅ Unban process completed.\n"
        f"📨 Failed to DM: {len(failed_dms)} members.",
        ephemeral=False
    )

keep_alive()
bot.run(TOKEN)
