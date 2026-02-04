import os
import logging
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio

# logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Token
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set")

# intents
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# yt-dlp / ffmpeg
YDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True,
}

FFMPEG_OPTIONS = {
    "options": "-vn",
}

# queues
music_queues = {}  # guild_id -> list of (url, title)

# helpers
def get_queue(guild_id):
    if guild_id not in music_queues:
        music_queues[guild_id] = []
    return music_queues[guild_id]

async def play_next(interaction: discord.Interaction):
    queue = get_queue(interaction.guild.id)
    vc = interaction.guild.voice_client

    if not queue:
        await interaction.channel.send("📭 Queue finished.")
        return

    audio_url, title = queue.pop(0)

    def after_play(err):
        if err:
            logger.error(f"Playback error: {err}")
        fut = asyncio.run_coroutine_threadsafe(
            play_next(interaction),
            bot.loop
        )
        try:
            fut.result()
        except Exception as e:
            logger.error(e)

    vc.play(
        discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS),
        after=after_play
    )

    await interaction.channel.send(f"🎵 Now playing: **{title}**")

# events
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception:
        logger.exception("Command sync failed")

# basic test
@bot.tree.command(name="hello", description="Say hi")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("Hi")

@bot.tree.command(name="ping", description="Latency")
async def ping(interaction: discord.Interaction):
    latency_ms=(bot.latency*1000)
    await interaction.response.send_message(f"Latency :{latency_ms}")

# voice
@bot.tree.command(name="join", description="Join your voice channel")
async def join(interaction: discord.Interaction):
    if not interaction.user.voice:
        await interaction.response.send_message(
            "You are not in a voice channel.", ephemeral=True
        )
        return

    channel = interaction.user.voice.channel

    if interaction.guild.voice_client:
        await interaction.guild.voice_client.move_to(channel)
    else:
        await channel.connect()

    await interaction.response.send_message(f"Joined **{channel}**")

@bot.tree.command(name="leave", description="Leave the voice channel")
async def leave(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc:
        await interaction.response.send_message(
            "I'm not in a voice channel!", ephemeral=True
        )
        return

    get_queue(interaction.guild.id).clear()
    await vc.disconnect()
    await interaction.response.send_message("Left the voice channel")

# play
@bot.tree.command(name="play", description="Add a YouTube link to queue")
@app_commands.describe(url="YouTube video URL")
async def play(interaction: discord.Interaction, url: str):
    if not interaction.user.voice:
        await interaction.response.send_message(
            "Join a voice channel first!", ephemeral=True
        )
        return

    vc = interaction.guild.voice_client
    if not vc:
        vc = await interaction.user.voice.channel.connect()

    await interaction.response.defer()

    try:
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info["url"]
            title = info.get("title", "Unknown")

        queue = get_queue(interaction.guild.id)
        queue.append((audio_url, title))

        if not vc.is_playing():
            await play_next(interaction)
        else:
            await interaction.followup.send(
                f"➕ Added to queue: **{title}**"
            )

    except Exception:
        logger.exception("Play failed")
        await interaction.followup.send("Failed to add this link.")

# run
bot.run(TOKEN)

