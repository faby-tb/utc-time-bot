import os
import discord
from discord.ext import tasks
from discord import app_commands
from dotenv import load_dotenv
from datetime import datetime, timezone
from flask import Flask
import threading

from supabase import create_client

# =========================
# ENV
# =========================
load_dotenv()

TOKEN = os.getenv("TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

VOICE_PREFIX = "🕒 UTC"

# =========================
# SUPABASE HELPERS
# =========================
def get_state(guild_id: int):
    res = sb.table("guild_settings").select("*").eq("guild_id", str(guild_id)).execute()

    if not res.data:
        return {"enabled": False, "channel_id": None, "last_update": None}

    return res.data[0]


def upsert_state(guild_id: int, **fields):
    data = {"guild_id": str(guild_id)}
    data.update(fields)

    sb.table("guild_settings").upsert(data).execute()


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
    db = sb.table("guild_settings").select("*").execute().data or []

    mapped = {g["guild_id"]: g for g in db}

    data = []

    for g in client.guilds:
        state = mapped.get(str(g.id), {
            "enabled": False,
            "channel_id": None,
            "last_update": None
        })

        data.append({
            "guild_id": g.id,
            "guild_name": g.name,
            "enabled": state["enabled"],
            "channel_id": state["channel_id"],
            "last_update": state["last_update"]
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

                const c = document.getElementById("content");
                c.innerHTML = "";

                data.guilds.forEach(g => {
                    const div = document.createElement("div");
                    div.className = "card";

                    div.innerHTML = `
                        <h3>${g.guild_name}</h3>
                        <p>Status: ${g.enabled ? "🟢 Enabled" : "🔴 Disabled"}</p>
                        <p>Channel: ${g.channel_id || "none"}</p>
                        <p>Last update: ${g.last_update || "never"}</p>
                    `;

                    c.appendChild(div);
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
async def get_channel(guild, channel_id):
    ch = guild.get_channel(int(channel_id)) if channel_id else None

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

    upsert_state(guild.id, channel_id=str(channel.id))
    return channel


async def force_update_guild(guild):

    state = get_state(guild.id)

    if not state.get("enabled"):
        return

    channel = await get_channel(guild, state.get("channel_id"))

    if not channel:
        channel = await create_clock(guild)

    hour = datetime.now(timezone.utc).strftime("%H:%M")

    await channel.edit(name=f"{VOICE_PREFIX} • {hour}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    upsert_state(guild.id, last_update=now)


# =========================
# COMMANDS
# =========================
@tree.command(name="clock")
async def clock(interaction: discord.Interaction, enabled: bool):

    if not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("No permission", ephemeral=True)

    upsert_state(interaction.guild.id, enabled=enabled)

    if enabled:
        await force_update_guild(interaction.guild)
        msg = "🟢 Enabled"
    else:
        msg = "🔴 Disabled"

    await interaction.response.send_message(msg, ephemeral=True)


@tree.command(name="clock_refresh")
async def clock_refresh(interaction: discord.Interaction):
    await force_update_guild(interaction.guild)

    now = datetime.now(timezone.utc).strftime("%H:%M UTC")

    await interaction.response.send_message(f"Updated → {now}", ephemeral=True)


@tree.command(name="utc")
async def utc(interaction: discord.Interaction):
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    await interaction.response.send_message(f"🕒 UTC time: **{now}**")


@tree.command(name="status")
async def status(interaction: discord.Interaction):

    state = get_state(interaction.guild.id)

    exists = False

    if state.get("channel_id"):
        try:
            ch = await interaction.guild.fetch_channel(int(state["channel_id"]))
            exists = ch is not None
        except:
            exists = False

    msg = (
        f"🟢 Enabled: {state.get('enabled')}\n"
        f"📡 Channel: {state.get('channel_id')}\n"
        f"🔗 Exists: {exists}\n"
        f"⏱ Last update: {state.get('last_update') or 'never'}"
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
        upsert_state(g.id)

    for g in client.guilds:
        state = get_state(g.id)

        if state.get("enabled"):
            await force_update_guild(g)

    update_all.start()
    update_presence.start()


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
        if get_state(g.id).get("enabled"):
            await force_update_guild(g)


# =========================
# START
# =========================
def start_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))

threading.Thread(target=start_flask, daemon=True).start()

client.run(TOKEN)