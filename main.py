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
import asyncio

# Import keep_alive so the bot stays online
import keep_alive

# Start the keep-alive server
keep_alive.keep_alive()

# Intents for member management
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.bans = True

bot = commands.Bot(command_prefix="!", intents=intents)

GUILD_ID = None  # Will be set on ready event

@bot.event
async def on_ready():
    global GUILD_ID
    print(f"✅ Logged in as {bot.user}")
    for guild in bot.guilds:
        GUILD_ID = guild.id
        print(f"Connected to: {guild.name} ({guild.id})")
    try:
        synced = await bot.tree.sync()
        print(f"🔹 Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Sync error: {e}")

@bot.tree.command(name="unban_all", description="Unban all banned members and send them a re-invite.")
async def unban_all(interaction: discord.Interaction):
    await interaction.response.send_message("⏳ Starting unban process... Please wait.", ephemeral=True)

    guild = bot.get_guild(GUILD_ID)
    if not guild:
        await interaction.followup.send("❌ Guild not found.")
        return

    try:
        # Create invite link (valid for 7 days, unlimited uses)
        invite = await list(guild.text_channels)[0].create_invite(max_age=604800, max_uses=0)
        invite_link = str(invite)
    except Exception as e:
        await interaction.followup.send(f"❌ Could not create invite: {e}")
        return

    bans = await guild.bans()
    total_bans = len(bans)
    await interaction.followup.send(f"🔹 Found {total_bans} banned members. Starting unban process...", ephemeral=True)

    success_count = 0
    fail_count = 0

    for ban_entry in bans:
        user = ban_entry.user
        try:
            # Unban user
            await guild.unban(user, reason="Mass unban via bot")
            success_count += 1

            # DM the user with message
            try:
                message = (
                    f"Hello {user.name},\n\n"
                    f"Our server was hacked and many members were banned by mistake. 😔\n"
                    f"We’ve fixed the issue, and you’re welcome to join us again!\n\n"
                    f"Here’s your invite link: {invite_link}\n\n"
                    f"Hope to see you back soon! ❤️"
                )
                await user.send(message)
            except:
                fail_count += 1

            await asyncio.sleep(1.5)  # Delay to avoid rate limits
        except Exception as e:
            fail_count += 1
            print(f"Error unbanning {user}: {e}")
            await asyncio.sleep(1.5)

    await interaction.followup.send(
        f"✅ Process complete!\n"
        f"Unbanned: **{success_count}**\n"
        f"Failed to message: **{fail_count}**"
    )

# Run bot
bot.run(os.getenv("BOT_TOKEN"))
