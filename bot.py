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
    enabled INTEGER DEFAULT 0,
    channel_id TEXT,
    last_update TEXT
)
""")

conn.commit()


# =========================
# ENABLE / DISABLE STATE
# =========================
def set_enabled(guild_id: int, value: bool):
    cursor.execute("""
        INSERT INTO guild_settings (guild_id, enabled)
        VALUES (?, ?)
        ON CONFLICT(guild_id)
        DO UPDATE SET enabled=excluded.enabled
    """, (str(guild_id), int(value)))

    conn.commit()


def is_enabled(guild_id: int) -> bool:
    cursor.execute("""
        SELECT enabled FROM guild_settings WHERE guild_id=?
    """, (str(guild_id),))

    row = cursor.fetchone()
    return bool(row[0]) if row else False

def set_last_update(guild_id: int, timestamp: str):
    cursor.execute("""
        INSERT INTO guild_settings (guild_id, last_update)
        VALUES (?, ?)
        ON CONFLICT(guild_id)
        DO UPDATE SET last_update=excluded.last_update
    """, (str(guild_id), timestamp))

    conn.commit()

def get_last_update(guild_id: int):
    cursor.execute("""
        SELECT last_update FROM guild_settings WHERE guild_id=?
    """, (str(guild_id),))

    row = cursor.fetchone()
    return row[0] if row else None


# =========================
# CHANNEL ID STORAGE
# =========================
def set_channel(guild_id: int, channel_id: int):
    cursor.execute("""
        INSERT INTO guild_settings (guild_id, channel_id)
        VALUES (?, ?)
        ON CONFLICT(guild_id)
        DO UPDATE SET channel_id=excluded.channel_id
    """, (str(guild_id), str(channel_id)))

    conn.commit()


def get_channel(guild_id: int):
    cursor.execute("""
        SELECT channel_id FROM guild_settings WHERE guild_id=?
    """, (str(guild_id),))

    row = cursor.fetchone()
    return int(row[0]) if row and row[0] else None

# =========================
# DISCORD BOT
# =========================
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


# =========================
# FLASK (KEEP ALIVE RENDER)
# =========================
app = Flask(__name__)

@app.route("/")
def home():
    return "UTC Bot alive"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))

@tree.command(name="status")
async def status(interaction: discord.Interaction):

    guild = interaction.guild

    enabled = is_enabled(guild.id)
    channel_id = get_channel(guild.id)

    channel_ok = False

    if channel_id:
        channel_ok = guild.get_channel(channel_id) is not None

    description = (
        f"🟢 Enabled: {enabled}\n"
        f"📡 Channel stored: {channel_id}\n"
        f"🔗 Channel exists: {channel_ok}"
    )

    await interaction.response.send_message(description, ephemeral=True)

@app.route("/api/guilds")
def api_guilds():

    guild_ids_db = {}

    cursor.execute("""
        SELECT guild_id, enabled, channel_id, last_update
        FROM guild_settings
    """)

    for g in cursor.fetchall():
        guild_ids_db[g[0]] = {
            "enabled": bool(g[1]),
            "channel_id": g[2],
            "last_update": g[3]
        }

    data = []

    for guild in client.guilds:

        db = guild_ids_db.get(str(guild.id), {
            "enabled": False,
            "channel_id": None,
            "last_update": None
        })

        data.append({
            "guild_id": guild.id,
            "guild_name": guild.name,
            "enabled": db["enabled"],
            "channel_id": db["channel_id"],
            "last_update": db["last_update"]
        })

    return {"guilds": data}

@app.route("/api/bot")
def bot_status():
    return {
        "latency": round(client.latency * 1000, 2),
        "guild_count": len(client.guilds),
        "status": "online"
    }

@app.route("/api/sync")
def api_sync():

    for guild in client.guilds:
        cursor.execute("""
            INSERT OR IGNORE INTO guild_settings (guild_id, enabled, channel_id, last_update)
            VALUES (?, 0, NULL, NULL)
        """, (str(guild.id),))

    conn.commit()

    return {"status": "synced"}

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
                        <h3>Server: ${g.guild_name}</h3>
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
# UTC HELPERS
# =========================
async def get_clock_channel(guild):

    channel_id = get_channel(guild.id)

    if not channel_id:
        return None

    channel = guild.get_channel(channel_id)
    if channel:
        return channel

    try:
        channel = await guild.fetch_channel(channel_id)
        return channel
    except:
        return None


async def create_clock(guild):

    # 🔥 primero busca si ya existe
    for ch in guild.voice_channels:
        if ch.name.startswith(VOICE_PREFIX):
            set_channel(guild.id, ch.id)
            return ch

    now = datetime.now(timezone.utc).strftime("%H:%M UTC")

    channel = await guild.create_voice_channel(
        f"{VOICE_PREFIX} • {now}"
    )

    set_channel(guild.id, channel.id)

    return channel


async def force_update_guild(guild):

    channel = await get_clock_channel(guild)

    if not channel:
        channel = await create_clock(guild)

    hour = datetime.now(timezone.utc).strftime("%H:%M")

    await channel.edit(
        name=f"{VOICE_PREFIX} • {hour}"
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    set_last_update(guild.id, now)

def get_status_text(guild_id: int) -> str:
    return "enabled" if is_enabled(guild_id) else "disabled"

def ensure_guild(guild_id: int):
    cursor.execute("""
        INSERT OR IGNORE INTO guild_settings (guild_id, enabled, channel_id, last_update)
        VALUES (?, 0, NULL, NULL)
    """, (str(guild_id),))
    conn.commit()

async def resync_from_discord(guild):
    """
    Reconstruye DB si se pierde estado
    """
    for ch in guild.voice_channels:
        if ch.name.startswith(VOICE_PREFIX):
            set_channel(guild.id, ch.id)
            return

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

    guild = interaction.guild

    set_enabled(guild.id, enabled)

    if enabled:

        await force_update_guild(guild)

        msg = "🟢 UTC clock enabled"

    else:

        msg = "🔴 UTC clock disabled"

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


# =========================
# EVENTS
# =========================
@client.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {client.user}")

    # 1. asegurar filas en DB
    for guild in client.guilds:
        ensure_guild(guild.id)

    # 2. reconstrucción + sync real
    for guild in client.guilds:

        if not is_enabled(guild.id):
            continue

        # 🔥 PASO CLAVE: intentar recuperar canal desde Discord
        channel = await get_clock_channel(guild)

        # 🔥 si DB no sirve, buscar en Discord directamente
        if not channel:
            channel = await resync_from_discord(guild)

        # 🔥 si todavía no existe, crear uno nuevo
        if not channel:
            channel = await create_clock(guild)

        # 🔥 actualización final
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
def start_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))

threading.Thread(target=start_flask, daemon=True).start()

client.run(TOKEN)