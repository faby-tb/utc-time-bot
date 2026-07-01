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
# SQLITE (PERSISTENTE REAL)
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
# DB - SINGLE SOURCE OF TRUTH
# =========================
def set_state(guild_id: int, *, enabled=None, channel_id=None, last_update=None):
    cursor.execute("""
        INSERT INTO guild_settings (guild_id, enabled, channel_id, last_update)
        VALUES (?, 0, NULL, NULL)
        ON CONFLICT(guild_id)
        DO UPDATE SET guild_id=guild_id
    """, (str(guild_id),))

    if enabled is not None:
        cursor.execute(
            "UPDATE guild_settings SET enabled=? WHERE guild_id=?",
            (int(enabled), str(guild_id))
        )

    if channel_id is not None:
        cursor.execute(
            "UPDATE guild_settings SET channel_id=? WHERE guild_id=?",
            (str(channel_id), str(guild_id))
        )

    if last_update is not None:
        cursor.execute(
            "UPDATE guild_settings SET last_update=? WHERE guild_id=?",
            (last_update, str(guild_id))
        )

    conn.commit()


def get_state(guild_id: int):
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


def ensure_guild(guild_id: int):
    cursor.execute("""
        INSERT OR IGNORE INTO guild_settings (guild_id, enabled, channel_id, last_update)
        VALUES (?, 0, NULL, NULL)
    """, (str(guild_id),))
    conn.commit()


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
    cursor.execute("SELECT guild_id, enabled, channel_id, last_update FROM guild_settings")
    db_rows = cursor.fetchall()

    db = {
        r[0]: {
            "enabled": bool(r[1]),
            "channel_id": r[2],
            "last_update": r[3]
        }
        for r in db_rows
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
        <title>UTC Bot</title>
        <style>
            body { font-family: Arial; background:#0f0f0f; color:white; }
            .card { padding:10px; margin:10px; background:#1c1c1c; border-radius:10px; }
        </style>
    </head>
    <body>
        <h1>🕒 UTC Bot Dashboard</h1>
        <div id="content"></div>

        <script>
            async function load(){
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
                        <p>Channel: ${g.channel_id || "none"}</p>
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
# CLOCK LOGIC
# =========================
async def get_clock_channel(guild):
    state = get_state(guild.id)
    channel_id = state["channel_id"]

    if not channel_id:
        return None

    ch = guild.get_channel(int(channel_id))
    if ch:
        return ch

    try:
        return await guild.fetch_channel(int(channel_id))
    except:
        return None


async def create_clock(guild):
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")

    channel = await guild.create_voice_channel(
        f"{VOICE_PREFIX} • {now}"
    )

    set_state(guild.id, channel_id=channel.id)

    return channel


async def force_update_guild(guild):
    state = get_state(guild.id)

    if not state["enabled"]:
        return

    channel = await get_clock_channel(guild)

    if not channel:
        channel = await create_clock(guild)

    hour = datetime.now(timezone.utc).strftime("%H:%M")

    await channel.edit(name=f"{VOICE_PREFIX} • {hour}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    set_state(guild.id, last_update=now)


# =========================
# COMMANDS
# =========================
@tree.command(name="clock")
async def clock(interaction: discord.Interaction, enabled: bool):

    if not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("No permission", ephemeral=True)

    set_state(interaction.guild.id, enabled=enabled)

    if enabled:
        await force_update_guild(interaction.guild)
        msg = "🟢 Enabled"
    else:
        msg = "🔴 Disabled"

    await interaction.response.send_message(msg, ephemeral=True)


@tree.command(name="clock_refresh")
async def clock_refresh(interaction: discord.Interaction):

    if not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("No permission", ephemeral=True)

    await force_update_guild(interaction.guild)

    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    await interaction.response.send_message(f"Updated → {now}", ephemeral=True)


@tree.command(name="utc")
async def utc(interaction: discord.Interaction):

    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    await interaction.response.send_message(f"🕒 UTC time: **{now} UTC**")


@tree.command(name="status")
async def status(interaction: discord.Interaction):

    state = get_state(interaction.guild.id)

    exists = False
    if state["channel_id"]:
        ch = interaction.guild.get_channel(int(state["channel_id"]))
        exists = ch is not None

    msg = (
        f"🟢 Enabled: {state['enabled']}\n"
        f"📡 Channel: {state['channel_id']}\n"
        f"🔗 Exists: {exists}\n"
        f"⏱ Last update: {state['last_update'] or 'never'}"
    )

    await interaction.response.send_message(msg, ephemeral=True)


# =========================
# EVENTS
# =========================
@client.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {client.user}")

    for g in client.guilds:
        ensure_guild(g.id)

    for g in client.guilds:
        state = get_state(g.id)

        if not state["enabled"]:
            continue

        await force_update_guild(g)

    update_all.start()
    update_presence.start()


@client.event
async def on_guild_join(guild):
    ensure_guild(guild.id)


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
        if get_state(g.id)["enabled"]:
            await force_update_guild(g)


# =========================
# START
# =========================
def start_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))

threading.Thread(target=start_flask, daemon=True).start()

client.run(TOKEN)