import os
import discord

from dotenv import load_dotenv

load_dotenv()

from datetime import datetime
from datetime import timezone

from discord.ext import tasks


TOKEN = os.getenv("TOKEN")

VOICE_PREFIX = "🕒 UTC"

intents = discord.Intents.default()

client = discord.Client(
    intents=intents
)

clock_channels = {}


async def find_or_create_clock(guild):

    for channel in guild.voice_channels:

        if channel.name.startswith(
            VOICE_PREFIX
        ):
            clock_channels[
                guild.id
            ] = channel

            return channel

    channel = await guild.create_voice_channel(
        f"{VOICE_PREFIX} • --:--"
    )

    clock_channels[
        guild.id
    ] = channel

    return channel


async def update_server(guild):

    try:

        channel = clock_channels.get(
            guild.id
        )

        if not channel:

            channel = await find_or_create_clock(
                guild
            )

        utc = datetime.now(
            timezone.utc
        )

        hour = utc.strftime(
            "%H:%M"
        )

        desired = (
            f"{VOICE_PREFIX} • {hour}"
        )

        if channel.name != desired:

            await channel.edit(
                name=desired
            )

    except Exception as e:

        print(
            guild.name,
            e
        )


@tasks.loop(minutes=5)
async def update_all():

    utc = datetime.now(
        timezone.utc
    )

    hour = utc.strftime(
        "%H:%M"
    )

    await client.change_presence(

        activity=discord.Activity(

            type=discord.ActivityType.watching,

            name=f"UTC {hour}"

        )

    )

    for guild in client.guilds:

        await update_server(
            guild
        )

    print(
        "Updated",
        hour
    )


@client.event
async def on_guild_join(
    guild
):

    print(
        "Joined",
        guild.name
    )

    await find_or_create_clock(
        guild
    )


@client.event
async def on_ready():

    print(
        client.user
    )

    for guild in client.guilds:

        await find_or_create_clock(
            guild
        )

    update_all.start()


client.run(
    TOKEN
)