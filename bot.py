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
# SQLITE
# =========================
conn = sqlite3.connect("settings.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id TEXT PRIMARY KEY,
    enabled INTEGER DEFAULT 0,
    channel_id TEXT,
    last_update TEXT
)
""")

conn.commit()

# =========================
# DB UNIFICADA (FIX CLAVE)
# =========================
def update_guild(guild_id: int, enabled=None, channel_id=None, last_update=None):

    cursor.execute("""
        INSERT INTO guild_settings (guild_id, enabled, channel_id, last_update)
        VALUES (?, COALESCE(?, 0), ?, ?)
        ON CONFLICT(guild_id)
        DO UPDATE SET
            enabled = COALESCE(excluded.enabled, guild_settings.enabled),
            channel_id = COALESCE(excluded.channel_id, guild_settings.channel_id),
            last_update = COALESCE(excluded.last_update, guild_settings.last_update)
    """, (
        str(guild_id),
        int(enabled) if enabled is not None else None,
        str(channel_id) if channel_id else None,
        last_update
    ))

    conn.commit()


def is_enabled(guild_id: int) -> bool:
    cursor.execute("SELECT enabled FROM guild_settings WHERE guild_id=?", (str(guild_id),))
    row = cursor.fetchone()
    return bool(row[0]) if row else False


def get_channel(guild_id: int):
    cursor.execute("SELECT channel_id FROM guild_settings WHERE guild_id=?", (str(guild_id),))
    row = cursor.fetchone()
    return int(row[0]) if row and row[0] else None


def get_last_update(guild_id: int):
    cursor.execute("SELECT last_update FROM guild_settings WHERE guild_id=?", (str(guild_id),))
    row = cursor.fetchone()
    return row[0] if row else None


# =========================
# DISCORD
# =========================
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# =========================
# FLASK
# =========================
app = Flask(__name__)

@app.route("/")
def home():
    return "UTC Bot alive"


@app.route("/api/guilds")
def api_guilds():
    cursor.execute("SELECT guild_id, enabled, channel_id, last_update FROM guild_settings")
    rows = cursor.fetchall()

    db = {
        r[0]: {
            "enabled": bool(r[1]),
            "channel_id": r[2],
            "last_update": r[3]
        }
        for r in rows
    }

    data = []

    for g in client.guilds:
        info = db.get(str(g.id), {
            "enabled": False,
            "channel_id": None,
            "last_update": None
        })

        data.append({
            "guild_id": g.id,
            "guild_name": g.name,
            "enabled": info["enabled"],
            "channel_id": info["channel_id"],
            "last_update": info["last_update"]
        })

    return {"guilds": data}


@app.route("/dashboard")
def dashboard():
    return """
    <html>
    <head>
        <title>UTC Bot Dashboard</title>
        <style>
            body { font-family: Arial; background:#0f0f0f; color:white; }
            .card { padding:10px; margin:10px; background:#1c1c1c; border-radius:10px; }
        </style>
    </head>
    <body>
        <h1>🕒 UTC Bot Dashboard</h1>
        <div id="content"></div>

        <script>
            async function load() {
                const res = await fetch('/api/guilds');
                const data = await res.json();

                const container = document.getElementById("content");

                data.guilds.forEach(g => {
                    const div = document.createElement("div");
                    div.className = "card";

                    div.innerHTML = `
                        <h3>${g.guild_name}</h3>
                        <p>Status: ${g.enabled ? "🟢 Enabled" : "🔴 Disabled"}</p>
                        <p>Channel ID: ${g.channel_id || "none"}</p>
                        <p>Last update: ${g.last_update || "never"}</p>
                    `;

                    container.appendChild(div);
                });
            }

            load();
        </script>
    </body>
    </html>
    """


# =========================
# UTC LOGIC
# =========================
async def get_clock_channel(guild):
    channel_id = get_channel(guild.id)

    if not channel_id:
        return None

    channel = guild.get_channel(channel_id)
    if channel:
        return channel

    try:
        return await guild.fetch_channel(channel_id)
    except:
        return None


async def create_clock(guild):
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")

    channel = await guild.create_voice_channel(
        f"{VOICE_PREFIX} • {now}"
    )

    update_guild(guild.id, channel_id=channel.id)

    return channel


async def force_update_guild(guild):
    channel = await get_clock_channel(guild)

    if not channel:
        channel = await create_clock(guild)

    hour = datetime.now(timezone.utc).strftime("%H:%M")

    await channel.edit(name=f"{VOICE_PREFIX} • {hour}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    update_guild(guild.id, last_update=now)


# =========================
# COMMANDS
# =========================
@tree.command(name="clock", description="Enable/disable UTC clock")
@app_commands.describe(enabled="true or false")
async def clock(interaction: discord.Interaction, enabled: bool):

    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("No permission", ephemeral=True)
        return

    update_guild(interaction.guild.id, enabled=enabled)

    if enabled:
        await force_update_guild(interaction.guild)
        msg = "🟢 Enabled"
    else:
        msg = "🔴 Disabled"

    await interaction.response.send_message(msg, ephemeral=True)


@tree.command(name="clock_refresh")
async def clock_refresh(interaction: discord.Interaction):

    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("No permission", ephemeral=True)
        return

    await force_update_guild(interaction.guild)

    now = datetime.now(timezone.utc).strftime("%H:%M UTC")

    await interaction.response.send_message(f"Updated → {now}", ephemeral=True)


@tree.command(name="utc")
async def utc(interaction: discord.Interaction):

    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    await interaction.response.send_message(f"🕒 {now}")

@tree.command(name="status", description="Show UTC clock status for this server")
async def status(interaction: discord.Interaction):

    guild = interaction.guild

    if guild is None:
        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True
        )
        return

    enabled = is_enabled(guild.id)
    channel_id = get_channel(guild.id)
    last_update = get_last_update(guild.id)

    channel_exists = False
    if channel_id:
        channel = guild.get_channel(channel_id)
        if not channel:
            try:
                channel = await guild.fetch_channel(channel_id)
            except:
                channel = None
        channel_exists = channel is not None

    description = (
        f"🟢 Enabled: {enabled}\n"
        f"📡 Channel ID: {channel_id}\n"
        f"🔗 Channel exists: {channel_exists}\n"
        f"⏱️ Last update: {last_update or 'never'}"
    )

    await interaction.response.send_message(description, ephemeral=True)


# =========================
# EVENTS
# =========================
@client.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {client.user}")

    for g in client.guilds:
        update_guild(g.id)  # asegura existencia

    for g in client.guilds:
        if is_enabled(g.id):
            await force_update_guild(g)

    update_all.start()
    update_presence.start()


@client.event
async def on_guild_join(guild):
    update_guild(guild.id)


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
    for g in client.guilds:
        if is_enabled(g.id):
            await force_update_guild(g)


# =========================
# START
# =========================
def start_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))


threading.Thread(target=start_flask, daemon=True).start()

client.run(TOKEN)