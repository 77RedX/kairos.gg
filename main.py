import os
import logging
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import time
from UI.info_view import InfoView, build_info_embed, format_uptime
from UI.queue_view import QueueView, build_queue_embed
from queuemgr.qmgr import QueueManager
os.makedirs("downloads", exist_ok=True) #making temp downloads directory
for f in os.listdir("downloads"):
    try:
        os.remove(os.path.join("downloads", f))
    except Exception:
        pass

# logging
import sys

# Force the Windows terminal to output UTF-8 so it doesn't crash on print
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
    handlers=[
        logging.FileHandler("kairos.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
BOT_START_TIME=time.time()

# Token
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set")

# intents
intents = discord.Intents.default()

bot = commands.Bot(command_prefix="!", intents=intents)

# yt-dlp / ffmpeg
YDL_OPTIONS = {
    "format": "bestaudio/bestaudio",
    "outtmpl": "downloads/%(id)s.%(ext)s",
    "quiet": True,
    "noplaylist": True,
}

FFMPEG_OPTIONS = {
    "options": "-vn",
}

queue_mgr = QueueManager(bot, FFMPEG_OPTIONS)

#helpers

def is_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")

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

@bot.tree.command(name="info", description="Show bot info")
async def info(interaction: discord.Interaction):
    embed, _ = build_info_embed(
        interaction, page=1, bot=bot, start_time=BOT_START_TIME
    )
    view = InfoView(
        interaction, bot=bot, start_time=BOT_START_TIME, page=1
    )
    await interaction.response.send_message(embed=embed, view=view)

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

    queue_mgr.clear(interaction.guild.id)
    queue_mgr.deleter.force_gc()
    await vc.disconnect()
    await interaction.response.send_message("Left the voice channel")

@bot.tree.command(name="skip", description="Skip the current track")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client

    if not vc:
        await interaction.response.send_message(
            "I'm not in a voice channel!", ephemeral=True
        )
        return

    if not vc.is_playing():
        await interaction.response.send_message(
            "Nothing is playing right now.", ephemeral=True
        )
        return

    queue_mgr.skip(interaction.guild.id)
    await interaction.response.send_message("⏭ Skipped.")

@bot.tree.command(name="stop", description="Stop playing")
async def stop(interaction: discord.Interaction):
    vc=interaction.guild.voice_client
    if not vc:
        await interaction.response.send_message("I'm not in a voice channel!", ephemeral=True)
        return
    
    queue_mgr.clear(interaction.guild.id)
    queue_mgr.deleter.force_gc()

    await interaction.response.send_message("Stopped playing.")
@bot.tree.command(name="pause", description="Pause the currently playing song")
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client

    if not vc:
        await interaction.response.send_message(
            "I'm not in a voice channel!", ephemeral=True
        )
        return

    if vc.is_playing():
        vc.pause()
        await interaction.response.send_message("⏸ **Paused.**")
    elif vc.is_paused():
        await interaction.response.send_message(
            "The music is already paused.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "Nothing is playing right now.", ephemeral=True
        )

@bot.tree.command(name="resume", description="Resume the paused song")
async def resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client

    if not vc:
        await interaction.response.send_message(
            "I'm not in a voice channel!", ephemeral=True
        )
        return

    if vc.is_paused():
        vc.resume()
        await interaction.response.send_message("▶️ **Resumed.**")
    elif vc.is_playing():
        await interaction.response.send_message(
            "The music is already playing.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "There is no paused music to resume.", ephemeral=True
        )

#queue

@bot.tree.command(name="queue", description="Show the music queue")
async def queue(interaction: discord.Interaction):
    current, q = queue_mgr.get_queue_snapshot(interaction.guild.id)

    embed = build_queue_embed(
        interaction.guild, current, q, page=1
    )
    view = QueueView(interaction, queue_mgr, page=1)

    await interaction.response.send_message(
        embed=embed,
        view=view
    )

# play
@bot.tree.command(name="play", description="Add a YouTube link to queue")
@app_commands.describe(url="YouTube link or song name")
async def play(interaction: discord.Interaction, url: str):
    if not interaction.user.voice:
        await interaction.response.send_message(
            "Join a voice channel first", ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True)
    status_msg = await interaction.followup.send(f"🔎 Searching for **{url}**...")
    vc = interaction.guild.voice_client
    if not vc:
        vc = await interaction.user.voice.channel.connect()

    try:
        loop = asyncio.get_running_loop()

        def extract():
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                if is_url(url):
                    info = ydl.extract_info(url, download=False)
                else:
                    info = ydl.extract_info(f"ytsearch:{url}", download=False)
                    if not info["entries"]:
                        return None
                    info = info["entries"][0]

                filename = ydl.prepare_filename(info)
                title = info.get("title", "Unknown")
                video_url = info.get("webpage_url")
                return filename, title, video_url

        result = await loop.run_in_executor(None, extract)

        if result is None:
            await interaction.followup.send("No results found.")
            return

        filename, title, video_url = result
        await status_msg.edit(content=f"➕ Added to queue: **{title}**")
        await queue_mgr.add(interaction, filename, title, video_url)

    except Exception:
        logger.exception("Play failed")
        await interaction.followup.send("Couldn't find song.")

# run
bot.run(TOKEN)
