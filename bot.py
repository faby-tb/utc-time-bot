import os
import discord
import threading

from dotenv import load_dotenv
from discord.ext import tasks
from discord import app_commands
from datetime import datetime, timezone
from flask import Flask

from supabase import create_client


# =========================
# ENV
# =========================
load_dotenv()

TOKEN = os.getenv("TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

sb = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

VOICE_PREFIX = "🕒 UTC"


# =========================
# SUPABASE
# =========================
def get_state(guild_id: int):

    res = (
        sb.table("guild_settings")
        .select("*")
        .eq("guild_id", str(guild_id))
        .execute()
    )

    if not res.data:

        return {
            "enabled": False,
            "channel_id": None,
            "last_update": None,
            "allowed_roles": []
        }

    state = res.data[0]

    state.setdefault(
        "allowed_roles",
        []
    )

    return state


def upsert_state(guild_id: int, **fields):

    data = {
        "guild_id": str(guild_id)
    }

    data.update(
        fields
    )

    (
        sb.table("guild_settings")
        .upsert(data)
        .execute()
    )


def can_manage_clock(member):

    if member.guild_permissions.administrator:
        return True

    state = get_state(
        member.guild.id
    )

    allowed = state.get(
        "allowed_roles",
        []
    )

    return any(
        str(role.id) in allowed
        for role in member.roles
    )


# =========================
# DISCORD
# =========================
intents = discord.Intents.default()

client = discord.Client(
    intents=intents
)

tree = app_commands.CommandTree(
    client
)


# =========================
# FLASK
# =========================
app = Flask(__name__)


@app.route("/")
def home():
    return "UTC Bot alive"


@app.route("/api/guilds")
def api():

    db = (
        sb.table("guild_settings")
        .select("*")
        .execute()
        .data
    )

    mapped = {
        x["guild_id"]: x
        for x in db
    }

    out = []

    for g in client.guilds:

        state = mapped.get(
            str(g.id),
            {}
        )

        out.append({
            "guild_id": g.id,
            "guild_name": g.name,
            "enabled": state.get("enabled"),
            "channel_id": state.get("channel_id"),
            "last_update": state.get("last_update")
        })

    return {
        "guilds": out
    }


@app.route("/dashboard")
def dashboard():

    return """
<html>
<body style='background:#111;color:white;font-family:Arial'>
<h1>🕒 UTC Dashboard</h1>
<div id='data'></div>

<script>

async function load(){

const r=
await fetch('/api/guilds');

const j=
await r.json();

const d=
document.getElementById("data");

d.innerHTML="";

j.guilds.forEach(g=>{

d.innerHTML+=`
<div style="
margin:10px;
padding:10px;
background:#222;
border-radius:12px">

<h3>${g.guild_name}</h3>

<p>${g.enabled?"🟢":"🔴"}</p>

<p>${g.last_update||"never"}</p>

</div>
`;

});

}

load();

setInterval(
load,
5000
);

</script>

</body>
</html>
"""


# =========================
# CLOCK
# =========================
async def get_channel(
    guild,
    channel_id
):

    if not channel_id:
        return None

    ch = guild.get_channel(
        int(channel_id)
    )

    if ch:
        return ch

    try:

        return await guild.fetch_channel(
            int(channel_id)
        )

    except:

        return None


async def create_clock(guild):

    now = (
        datetime
        .now(timezone.utc)
        .strftime("%H:%M")
    )

    ch = await guild.create_voice_channel(
        f"{VOICE_PREFIX} • {now}"
    )

    upsert_state(
        guild.id,
        channel_id=str(ch.id)
    )

    return ch


async def force_update_guild(guild):

    state = get_state(
        guild.id
    )

    if not state.get(
        "enabled"
    ):
        return

    ch = await get_channel(
        guild,
        state.get(
            "channel_id"
        )
    )

    if not ch:

        ch = await create_clock(
            guild
        )

    hour = (
        datetime
        .now(timezone.utc)
        .strftime("%H:%M")
    )

    await ch.edit(
        name=f"{VOICE_PREFIX} • {hour}"
    )

    upsert_state(
        guild.id,
        last_update=datetime.now(
            timezone.utc
        ).isoformat()
    )


# =========================
# COMMANDS
# =========================
@tree.command()
async def clock(
    interaction: discord.Interaction,
    enabled: bool
):

    if not can_manage_clock(
        interaction.user
    ):

        return await interaction.response.send_message(
            "No permission",
            ephemeral=True
        )

    upsert_state(
        interaction.guild.id,
        enabled=enabled
    )

    if enabled:

        await force_update_guild(
            interaction.guild
        )

    await interaction.response.send_message(
        f"{'🟢 Enabled' if enabled else '🔴 Disabled'}",
        ephemeral=True
    )


@tree.command()
async def clock_refresh(
    interaction: discord.Interaction
):

    if not can_manage_clock(
        interaction.user
    ):

        return await interaction.response.send_message(
            "No permission",
            ephemeral=True
        )

    await force_update_guild(
        interaction.guild
    )

    await interaction.response.send_message(
        "Updated",
        ephemeral=True
    )


@tree.command()
async def utc(
    interaction: discord.Interaction
):

    now = (
        datetime
        .now(timezone.utc)
        .strftime("%H:%M UTC")
    )

    await interaction.response.send_message(
        f"🕒 UTC time: **{now}**"
    )


@tree.command(
    name="status",
    description="Show UTC Clock status"
)
async def status(
    interaction: discord.Interaction
):

    state = get_state(
        interaction.guild.id
    )

    enabled = (
        "🟢 Enabled"
        if state.get("enabled")
        else "🔴 Disabled"
    )

    channel = state.get(
        "channel_id"
    )

    channel_text = (
        f"<#{channel}"
        if channel
        else "None"
    )

    updated = (
        state.get(
            "last_update"
        )
        or "Never"
    )

    roles = state.get(
        "allowed_roles",
        []
    )

    role_text = (
        "\n".join(
            f"<@&{r}>"
            for r in roles
        )
        if roles
        else "Administrators only"
    )

    embed = discord.Embed(

        title="🕒 UTC Clock Status",

        description=(
            "Current configuration "
            "for this server"
        ),

        color=discord.Color.blurple()

    )

    embed.add_field(
        name="Status",
        value=enabled,
        inline=False
    )

    embed.add_field(
        name="Clock Channel",
        value=channel_text,
        inline=False
    )

    embed.add_field(
        name="Last Update",
        value=f"`{updated}`",
        inline=False
    )

    embed.add_field(
        name="Allowed Roles",
        value=role_text,
        inline=False
    )

    embed.set_footer(
        text=f"Server ID • {interaction.guild.id}"
    )

    embed.set_thumbnail(
        url=client.user.display_avatar.url
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


@tree.command()
async def clock_role_add(
    interaction: discord.Interaction,
    role: discord.Role
):

    if not interaction.user.guild_permissions.administrator:

        return await interaction.response.send_message(
            "Administrator only",
            ephemeral=True
        )

    state = get_state(
        interaction.guild.id
    )

    roles = state.get(
        "allowed_roles",
        []
    )

    rid = str(
        role.id
    )

    if rid not in roles:

        roles.append(
            rid
        )

    upsert_state(
        interaction.guild.id,
        allowed_roles=roles
    )

    await interaction.response.send_message(
        f"{role.mention} added",
        ephemeral=True
    )


@tree.command()
async def clock_role_remove(
    interaction: discord.Interaction,
    role: discord.Role
):

    if not interaction.user.guild_permissions.administrator:

        return

    state = get_state(
        interaction.guild.id
    )

    roles = state.get(
        "allowed_roles",
        []
    )

    rid = str(
        role.id
    )

    if rid in roles:

        roles.remove(
            rid
        )

    upsert_state(
        interaction.guild.id,
        allowed_roles=roles
    )

    await interaction.response.send_message(
        "Removed",
        ephemeral=True
    )


@tree.command()
async def clock_roles(
    interaction: discord.Interaction
):

    roles = get_state(
        interaction.guild.id
    ).get(
        "allowed_roles",
        []
    )

    msg = "\n".join(
        f"<@&{x}>"
        for x in roles
    )

    await interaction.response.send_message(
        msg or "No roles",
        ephemeral=True
    )


# =========================
# EVENTS
# =========================
@client.event
async def on_ready():

    await tree.sync()

    print(
        client.user
    )

    for g in client.guilds:

        upsert_state(
            g.id
        )

        if get_state(
            g.id
        ).get(
            "enabled"
        ):

            await force_update_guild(
                g
            )

    update_all.start()
    update_presence.start()


# =========================
# LOOPS
# =========================
last_hour = None


@tasks.loop(seconds=60)
async def update_presence():

    global last_hour

    hour = (
        datetime
        .now(timezone.utc)
        .strftime("%H:%M")
    )

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

        await force_update_guild(
            g
        )


# =========================
# START
# =========================
def start_flask():

    app.run(
        host="0.0.0.0",
        port=int(
            os.getenv(
                "PORT",
                3000
            )
        )
    )


threading.Thread(
    target=start_flask,
    daemon=True
).start()

client.run(
    TOKEN
)