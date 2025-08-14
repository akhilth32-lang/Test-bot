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

# ✅ Keep-alive server (Render)
import keep_alive
keep_alive.keep_alive()

# Bot intents
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.bans = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")
    for guild in bot.guilds:
        print(f"Connected to: {guild.name} ({guild.id})")
    try:
        synced = await bot.tree.sync()
        print(f"🔹 Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Sync error: {e}")

@bot.tree.command(name="unban_all", description="Unban all banned members and send them a re-invite.")
async def unban_all(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)  # Prevents timeout

    guild = interaction.guild
    if not guild:
        await interaction.followup.send("❌ This command must be used inside a server.")
        return

    # Check bot permissions
    if not guild.me.guild_permissions.ban_members:
        await interaction.followup.send("❌ I don’t have permission to unban members.")
        return

    bans = await guild.bans()
    total_bans = len(bans)

    if total_bans == 0:
        await interaction.followup.send("✅ No banned members found.")
        return

    try:
        invite = await list(guild.text_channels)[0].create_invite(max_age=604800, max_uses=0)
        invite_link = str(invite)
    except Exception as e:
        await interaction.followup.send(f"❌ Could not create invite: {e}")
        return

    success_count = 0
    fail_count = 0

    for i, ban_entry in enumerate(bans, start=1):
        user = ban_entry.user
        print(f"🔄 Unbanning: {user} ({user.id})")  # Debug log

        try:
            await guild.unban(user, reason="Mass unban via bot")
            success_count += 1
            try:
                await user.send(
                    f"Hello {user.name},\n\n"
                    f"Our server was hacked and many members were banned by mistake. 😔\n"
                    f"We’ve fixed the issue, and you’re welcome to join us again!\n\n"
                    f"Here’s your invite link: {invite_link}\n\n"
                    f"Hope to see you back soon! ❤️"
                )
            except:
                fail_count += 1
        except Exception as e:
            fail_count += 1
            print(f"❌ Error unbanning {user}: {e}")

        # Show progress
        await interaction.followup.send(f"Progress: {i}/{total_bans} unbanned.", ephemeral=False)
        await asyncio.sleep(1.5)  # Prevent rate limits

    await interaction.followup.send(
        f"✅ Finished!\n"
        f"Unbanned: **{success_count}**\n"
        f"Failed to message: **{fail_count}**"
    )

# Run bot
bot.run(os.getenv("BOT_TOKEN"))
