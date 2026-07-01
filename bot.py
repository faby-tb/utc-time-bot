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
# SQLITE (PERSISTENCIA REAL)
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
# DB CORE (FIX REAL)
# =========================
def update_guild(guild_id: int, enabled=None, channel_id=None, last_update=None):

    cursor.execute("""
        INSERT INTO guild_settings (guild_id, enabled, channel_id, last_update)
        VALUES (?, COALESCE(?, 0), ?, ?)
        ON CONFLICT(guild_id)
        DO UPDATE SET
            enabled = COALESCE(?, enabled),
            channel_id = COALESCE(?, channel_id),
            last_update = COALESCE(?, last_update)
    """, (
        str(guild_id),

        int(enabled) if enabled is not None else None,
        str(channel_id) if channel_id else None,
        last_update,

        int(enabled) if enabled is not None else None,
        str(channel_id) if channel_id else None,
        last_update
    ))

    conn.commit()


def get_guild(guild_id: int):
    cursor.execute("""
        SELECT enabled, channel_id, last_update
        FROM guild_settings
        WHERE guild_id=?
    """, (str(guild_id),))

    row = cursor.fetchone()

    if not row:
        return {"enabled": False, "channel_id": None, "last_update": None}

    return {
        "enabled": bool(row[0]),
        "channel_id": row[1],
        "last_update": row[2]
    }


# =========================
# DISCORD
# =========================
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# =========================
# FLASK DASHBOARD
# =========================
app = Flask(__name__)


@app.route("/")
def home():
    return "UTC Bot alive"


@app.route("/api/guilds")
def api_guilds():

    data = []

    for g in client.guilds:
        db = get_guild(g.id)

        data.append({
            "guild_id": g.id,
            "guild_name": g.name,
            "enabled": db["enabled"],
            "channel_id": db["channel_id"],
            "last_update": db["last_update"]
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
                container.innerHTML = "";

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
            setInterval(load, 5000);
        </script>
    </body>
    </html>
    """


# =========================
# UTC LOGIC
# =========================
async def get_clock_channel(guild):

    db = get_guild(guild.id)
    channel_id = db["channel_id"]

    if not channel_id:
        return None

    channel = guild.get_channel(int(channel_id))
    if channel:
        return channel

    try:
        return await guild.fetch_channel(int(channel_id))
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
    await interaction.response.send_message(f"🕒 UTC time: **{now} UTC**")


@tree.command(name="status", description="Show status")
async def status(interaction: discord.Interaction):

    db = get_guild(interaction.guild.id)

    await interaction.response.send_message(
        f"🟢 Enabled: {db['enabled']}\n"
        f"📡 Channel: {db['channel_id']}\n"
        f"⏱️ Last update: {db['last_update']}",
        ephemeral=True
    )


# =========================
# EVENTS
# =========================
@client.event
async def on_ready():

    await tree.sync()
    print("Bot ready")

    for g in client.guilds:
        update_guild(g.id)

    for g in client.guilds:
        if get_guild(g.id)["enabled"]:
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
        if get_guild(g.id)["enabled"]:
            await force_update_guild(g)


# =========================
# START
# =========================
def start_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))


threading.Thread(target=start_flask, daemon=True).start()

client.run(TOKEN)