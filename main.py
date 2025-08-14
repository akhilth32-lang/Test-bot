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
from discord import app_commands
from discord.ext import commands
from keep_alive import keep_alive

# === CONFIG ===
GUILD_ID = 1352037302590902462  # Your server ID
BOT_TOKEN = os.getenv("BOT_TOKEN")

# === BOT SETUP ===
intents = discord.Intents.default()
intents.bans = True  # Needed to fetch bans
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"✅ Slash commands synced to guild {GUILD_ID}")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

# === UNBAN ALL COMMAND ===
@bot.tree.command(name="unban_all", description="Unban all members and send them an invite link.")
async def unban_all(interaction: discord.Interaction):
    await interaction.response.send_message("⏳ Starting unban process... Please wait.", ephemeral=False)

    guild = bot.get_guild(GUILD_ID)
    if not guild:
        await interaction.followup.send("❌ Guild not found. Check GUILD_ID.", ephemeral=True)
        return

    # Check permissions
    me = guild.get_member(bot.user.id)
    if not me.guild_permissions.ban_members:
        await interaction.followup.send("❌ I don't have permission to unban members.", ephemeral=True)
        return
    if not me.guild_permissions.create_instant_invite:
        await interaction.followup.send("❌ I don't have permission to create invite links.", ephemeral=True)
        return

    try:
        bans = await guild.bans()
        total_bans = len(bans)
        if total_bans == 0:
            await interaction.followup.send("✅ No banned members found.")
            return

        invite = await guild.text_channels[0].create_invite(max_age=86400, max_uses=0, unique=True)
        count = 0

        for ban_entry in bans:
            user = ban_entry.user
            try:
                await guild.unban(user, reason="Mass unban after server hack.")
                try:
                    await user.send(
                        f"🚨 Someone hacked the server and banned all members!\n"
                        f"Please join back: {invite.url}"
                    )
                except:
                    pass  # Can't DM some users

                count += 1
                if count % 10 == 0:
                    await interaction.followup.send(f"🔄 Unbanned {count}/{total_bans} members...", ephemeral=False)

            except Exception as e:
                print(f"Failed to unban {user}: {e}")

        await interaction.followup.send(f"✅ Finished unbanning {count} members. Invite sent to DMs.")

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

# === KEEP ALIVE & RUN ===
keep_alive()
bot.run(BOT_TOKEN)
