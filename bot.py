import os
import sqlite3
import threading
import discord

from dotenv import load_dotenv
from discord.ext import tasks
from datetime import datetime, timezone
from discord import app_commands
from flask import Flask

# =========================
# ENV
# =========================
load_dotenv()
TOKEN = os.getenv("TOKEN")

VOICE_PREFIX = "🕒 UTC"

# =========================
# SQLITE (PERSISTENCIA)
# =========================
conn = sqlite3.connect("settings.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id TEXT PRIMARY KEY,
    enabled INTEGER DEFAULT 0
)
""")
conn.commit()


def set_enabled(guild_id: int, value: bool):
    cursor.execute("""
        INSERT INTO guild_settings (guild_id, enabled)
        VALUES (?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET enabled=excluded.enabled
    """, (str(guild_id), int(value)))
    conn.commit()


def is_enabled(guild_id: int) -> bool:
    cursor.execute("""
        SELECT enabled FROM guild_settings WHERE guild_id=?
    """, (str(guild_id),))
    row = cursor.fetchone()
    return bool(row[0]) if row else False


# =========================
# FLASK (KEEP ALIVE RENDER)
# =========================
app = Flask(__name__)

@app.route("/")
def home():
    return "UTC Bot alive"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))


# =========================
# DISCORD BOT
# =========================
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


# =========================
# UTC HELPERS
# =========================
async def get_clock_channel(guild):
    for ch in guild.voice_channels:
        if ch.name.startswith(VOICE_PREFIX):
            return ch
    return None


async def create_clock(guild):
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    return await guild.create_voice_channel(
        f"{VOICE_PREFIX} • {now}"
    )


async def force_update_guild(guild):
    channel = await get_clock_channel(guild)

    if not channel:
        channel = await create_clock(guild)

    hour = datetime.now(timezone.utc).strftime("%H:%M")

    await channel.edit(
        name=f"{VOICE_PREFIX} • {hour}"
    )

def get_status_text(guild_id: int) -> str:
    return "enabled" if is_enabled(guild_id) else "disabled"

# =========================
# SLASH COMMANDS
# =========================
@tree.command(name="clock", description="Enable or disable UTC clock")
@app_commands.describe(enabled="true or false")
async def clock(interaction: discord.Interaction, enabled: bool):

    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "Need Manage Server permission",
            ephemeral=True
        )
        return

    set_enabled(interaction.guild.id, enabled)

    if enabled:
        await create_clock(interaction.guild)
        await force_update_guild(interaction.guild)
        msg = "UTC clock enabled"
    else:
        msg = "UTC clock disabled"

    await interaction.response.send_message(msg, ephemeral=True)


@tree.command(name="clock_refresh", description="Force update UTC clock")
async def clock_refresh(interaction: discord.Interaction):

    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "Need Manage Server permission",
            ephemeral=True
        )
        return

    await force_update_guild(interaction.guild)

    now = datetime.now(timezone.utc).strftime("%H:%M UTC")

    await interaction.response.send_message(
        f"Clock updated → {now} ✅",
        ephemeral=True
    )


@tree.command(name="utc", description="Show current UTC time")
async def utc(interaction: discord.Interaction):

    now = datetime.now(timezone.utc).strftime("%H:%M UTC")

    await interaction.response.send_message(
        f"🕒 UTC time: **{now}**"
    )

@tree.command(name="status", description="Show UTC clock status for this server")
async def status(interaction: discord.Interaction):

    guild = interaction.guild

    if guild is None:
        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True
        )
        return

    status = is_enabled(guild.id)

    if status:
        description = (
            "🟢 UTC Clock is **ENABLED**\n"
            "The bot is updating the voice channel every minute."
        )
    else:
        description = (
            "🔴 UTC Clock is **DISABLED**\n"
            "Use /clock enabled:true to activate it."
        )

    await interaction.response.send_message(
        description,
        ephemeral=True
    )

# =========================
# EVENTS
# =========================
@client.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {client.user}")

    for guild in client.guilds:

        if not is_enabled(guild.id):
            continue

        await force_update_guild(guild)

    update_all.start()
    update_presence.start()


@client.event
async def on_guild_join(guild):

    if is_enabled(guild.id):
        await force_update_guild(guild)


# =========================
# LOOPS
# =========================
last_hour = None

@tasks.loop(seconds=60)
async def update_presence():
    global last_hour

    hour = datetime.now(timezone.utc).strftime("%H:%M")

    if hour != last_hour:
        last_hour = hour

        await client.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"🕒 UTC {hour}"
            )
        )


@tasks.loop(minutes=5)
async def update_all():

    for guild in client.guilds:
        if is_enabled(guild.id):
            await force_update_guild(guild)


# =========================
# STARTUP
# =========================
threading.Thread(target=run_web).start()
client.run(TOKEN)