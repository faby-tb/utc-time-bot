import os
import json
import discord

from dotenv import load_dotenv
from discord.ext import tasks
from datetime import datetime, timezone
from discord import app_commands

load_dotenv()

TOKEN = os.getenv("TOKEN")

VOICE_PREFIX = "🕒 UTC"

SETTINGS_FILE = "settings.json"

last_hour = None

intents = discord.Intents.default()

client = discord.Client(
    intents=intents
)

tree = app_commands.CommandTree(
    client
)

clock_channels = {}


def load_settings():

    try:

        with open(
            SETTINGS_FILE,
            "r",
            encoding="utf8"
        ) as f:

            return json.load(f)

    except:

        return {}


def save_settings(data):

    with open(
        SETTINGS_FILE,
        "w",
        encoding="utf8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2
        )


settings = load_settings()


def enabled(guild_id):

    return settings.get(
        str(guild_id),
        False
    )


async def create_clock(guild):

    await guild.fetch_channels()

    for ch in guild.voice_channels:

        if ch.name.startswith(
            VOICE_PREFIX
        ):

            clock_channels[
                guild.id
            ] = ch

            return ch

    ch = await guild.create_voice_channel(
        f"{VOICE_PREFIX} • --:--"
    )

    clock_channels[
        guild.id
    ] = ch

    return ch


async def delete_clock(guild):

    for ch in guild.voice_channels:

        if ch.name.startswith(
            VOICE_PREFIX
        ):

            await ch.delete()


@tree.command(
    name="clock",
    description="Enable or disable UTC clock"
)
@app_commands.describe(
    enabled="true enable / false disable"
)
async def clock(
    interaction: discord.Interaction,
    enabled: bool
):

    guild = interaction.guild

    if guild is None:
        return

    if not interaction.user.guild_permissions.manage_guild:

        await interaction.response.send_message(
            "Need Manage Server",
            ephemeral=True
        )

        return

    settings[
        str(guild.id)
    ] = enabled

    save_settings(
        settings
    )

    if enabled:

        await create_clock(
            guild
        )

        msg = (
            "UTC clock enabled"
        )

    else:

        await delete_clock(
            guild
        )

        await force_update_guild(
            guild
        )

        msg = (
            "UTC clock disabled"
        )

    await interaction.response.send_message(
        msg,
        ephemeral=True
    )

@tree.command(
    name="clock_refresh",
    description="Force update the UTC clock in this server"
)
async def clock_refresh(interaction: discord.Interaction):

    guild = interaction.guild

    if guild is None:
        return

    # permisos (opcional pero recomendado)
    if not interaction.user.guild_permissions.manage_guild:

        await interaction.response.send_message(
            "Need Manage Server permission",
            ephemeral=True
        )

        return

    await force_update_guild(guild)

    await interaction.response.send_message(
        f"Clock updated → {datetime.now(timezone.utc).strftime('%H:%M UTC')}✅",
        ephemeral=True
    )

@tree.command(
    name="utc",
    description="Show current UTC time"
)
async def utc(interaction: discord.Interaction):

    now = datetime.now(timezone.utc).strftime("%H:%M UTC")

    await interaction.response.send_message(
        f"🕒 UTC time: **{now}**"
    )


async def force_update_guild(guild):

    channel = clock_channels.get(guild.id)

    if not channel:

        channel = await create_clock(guild)

    utc = datetime.now(timezone.utc)
    hour = utc.strftime("%H:%M")

    try:
        await channel.edit(
            name=f"{VOICE_PREFIX} • {hour}"
        )

    except Exception as e:

        print(guild.name, e)

@client.event
async def on_guild_join(guild):

    if enabled(guild.id):

        await create_clock(guild)

        await force_update_guild(guild)


@tasks.loop(seconds=60)
async def update_presence():

    global last_hour

    utc = datetime.now(
        timezone.utc
    )

    hour = utc.strftime(
        "%H:%M"
    )

    if hour != last_hour:

        last_hour = hour

        await client.change_presence(

            activity=discord.Activity(

                type=discord.ActivityType.watching,

                name=f"🕒 UTC {hour}"

            )

        )

@tasks.loop(
    minutes=15
)
async def update_all():


    for guild in client.guilds:

        if not enabled(guild.id):
            continue

        await force_update_guild(guild)



@client.event
async def on_ready():

    await tree.sync()

    print(client.user)

    for guild in client.guilds:

        if enabled(guild.id):

            await create_clock(guild)

            await force_update_guild(guild)

    update_all.start()
    update_presence.start()

client.run(
    TOKEN
)