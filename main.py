import os
import logging
from logging.handlers import RotatingFileHandler
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import time
from UI.info_view import InfoView, build_info_embed
from UI.queue_view import QueueView, build_queue_embed
from queuemgr.qmgr import QueueManager
from queuemgr.playback import fetch_search_results
from UI.search_view import SearchMenu
from database.database import init_db, get_db_stats, get_recommendations, get_seed_track
import sys
from UI.vibe_selector import VibeSelector
from UI.recommend_view import RecommendView

os.makedirs("downloads", exist_ok=True) #making temp downloads directory
for f in os.listdir("downloads"):
    try:
        os.remove(os.path.join("downloads", f))
    except Exception:
        pass

# logging

# Force the Windows terminal to output UTF-8 so it doesn't crash on print
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "kairos.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
    handlers=[
        RotatingFileHandler(
            LOG_FILE, 
            maxBytes=5 * 1024 * 1024, # 5 MB size limit per file
            backupCount=5,            # Keep a maximum of 5 older log files
            encoding="utf-8"
        ),
        logging.StreamHandler(sys.stdout)
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
    "format": "bestaudio/best",        # Standardize with playback.py
    "quiet": True,
    "noplaylist": True,
    #"extract_flat": "in_playlist",    # Helps search speed and reliability
    "ignoreerrors": True,             # Don't crash if one search result is dead
    "no_warnings": True,
    "nocheckcertificate": True,
    "js_runtimes": {"node": {}},
}

FFMPEG_OPTIONS = {
    "options": "-vn",
}

queue_mgr = QueueManager(bot, FFMPEG_OPTIONS)
active_text_channels = {}

# --- helpers ---

def is_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")

async def process_play_request(interaction: discord.Interaction, url: str):

    active_text_channels[interaction.guild.id] = interaction.channel

    """Shared logic for both /play and /search to extract and queue music."""
    if not interaction.user.voice:
        if not interaction.response.is_done():
            await interaction.response.send_message("Join a voice channel first", ephemeral=True)
        else:
            await interaction.followup.send("Join a voice channel first", ephemeral=True)
        return

    # Handle Discord interaction states gracefully
    if not interaction.response.is_done():
        await interaction.response.defer(thinking=True)
        status_msg = await interaction.followup.send(f"🔎 Processing **{url}**...")
    else:
        status_msg = await interaction.followup.send(f"🔎 Processing **{url}**...")

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
                    if not info or not info.get("entries"):
                        return None
                    info = info["entries"][0]

                duration = info.get("duration")
                if duration and duration > 1800: # 1800 seconds = 30 minutes
                    return "TOO_LONG"

                filename = ydl.prepare_filename(info)
                title = info.get("title", "Unknown")
                video_url = info.get("webpage_url", url)
                return filename, title, video_url

        result = await loop.run_in_executor(None, extract)

        if result == "TOO_LONG":
            await status_msg.edit(content="❌ This song file can't be fetched.")
            return
        elif result is None:
            await status_msg.edit(content="❌ No results found.")
            return

        filename, title, video_url = result
        await status_msg.edit(content=f"➕ Added to queue: **{title}**")
        await queue_mgr.add(interaction, filename, title, video_url)

    except Exception:
        logger.exception("Play failed")
        await status_msg.edit(content="❌ Couldn't find song.")


# --- events ---
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")

    queue_mgr.inference_queue.start()
    logger.info("✅ Background audio workers started!")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception:
        logger.exception("Command sync failed")

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    """Handles auto-cleanup when the bot is disconnected or left alone in a VC."""
    vc = member.guild.voice_client

    # SCENARIO 1: The bot itself was disconnected (by Discord, by a network drop, or kicked)
    if member == bot.user and before.channel and not after.channel:
        logger.info(f"Bot was disconnected from {member.guild.name}. Clearing queue.")
        queue_mgr.clear(member.guild.id)
        queue_mgr.deleter.force_gc()
        return

    # SCENARIO 2: A user left the channel. Is the bot alone now?
    if vc and vc.channel:
        # Count members in the bot's channel who are NOT bots
        non_bot_members = [m for m in vc.channel.members if not m.bot]
        
        if len(non_bot_members) == 0:
            logger.info(f"Bot left alone in {member.guild.name}. Auto-disconnecting.")
            queue_mgr.clear(member.guild.id)
            queue_mgr.deleter.force_gc()
            await vc.disconnect()

            text_channel = active_text_channels.get(member.guild.id)
            if text_channel:
                try:
                    await text_channel.send("👋 **All users disconnected.**")
                except Exception as e:
                    logger.error(f"Could not send disconnect message: {e}")

# basic test
@bot.tree.command(name="hello", description="Say hi")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("Hi")

@bot.tree.command(name="ping", description="Latency")
async def ping(interaction: discord.Interaction):
    latency_ms=(bot.latency*1000)
    await interaction.response.send_message(f"Latency :{latency_ms:.0f}ms")

@bot.tree.command(name="info", description="Show bot info")
async def info(interaction: discord.Interaction):
    embed, _ = build_info_embed(
        interaction, page=1, bot=bot, start_time=BOT_START_TIME
    )
    view = InfoView(
        interaction, bot=bot, start_time=BOT_START_TIME, page=1
    )
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="brain", description="Check the size and current vibe of KaiROS's memory.")
async def brain(interaction: discord.Interaction):
    count, avg_v, avg_a = get_db_stats()

    # Determine the "Global Vibe" text based on the quadrants
    if count == 0:
        vibe_str = "Brain is empty. Play some music!"
    elif avg_v > 0 and avg_a > 0:
        vibe_str = "Happy & Energetic ☀️"
    elif avg_v > 0 and avg_a <= 0:
        vibe_str = "Peaceful & Chill 🍃"
    elif avg_v <= 0 and avg_a > 0:
        vibe_str = "Aggressive & Intense 🔥"
    else:
        vibe_str = "Melancholic & Dark 🌧️"

    # Build a sleek Discord Embed
    embed = discord.Embed(
        title="🧠 KaiROS Neural Memory",
        description="Here is what I have learned from listening to your queues.",
        color=discord.Color.purple()
    )
    
    embed.add_field(name="Total Songs Learned", value=f"**{count}** unique tracks", inline=False)
    
    if count > 0:
        embed.add_field(name="Global Vibe", value=vibe_str, inline=True)
        embed.add_field(name="Average Coordinates", value=f"V: {avg_v:.2f} | A: {avg_a:.2f}", inline=True)
    
    await interaction.response.send_message(embed=embed)

# voice
@bot.tree.command(name="join", description="Join your voice channel")
async def join(interaction: discord.Interaction):
    active_text_channels[interaction.guild.id] = interaction.channel
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

@bot.tree.command(name="search", description="Search YouTube and pick a song")
async def search_command(interaction: discord.Interaction, query: str):
    await interaction.response.defer(ephemeral=True) 
    
    results = await fetch_search_results(query, limit=15)
    
    if not results:
        await interaction.followup.send("❌ No results found for that query.")
        return

    # Call the new shared helper!
    async def on_song_selected(inter: discord.Interaction, selected_url: str):
        await process_play_request(inter, selected_url) 

    view = SearchMenu(results, play_callback=on_song_selected)
    await interaction.followup.send("Here are the top results:", view=view)

@bot.tree.command(name="recommend", description="Get 5 vibe-matched songs based on what is currently playing.")
async def recommend(interaction: discord.Interaction):
    await interaction.response.defer() 

    # 1. Get the song currently playing in this specific server
    current, _ = queue_mgr.get_queue_snapshot(interaction.guild.id)
    
    if not current:
        await interaction.followup.send("⚠️ There is no music playing right now to base recommendations on!")
        return
        
    current_url = current[2]

    # 2. Ask the database for the coordinates AND the new metadata
    seed_track = get_seed_track(current_url, str(interaction.guild.id))

    if not seed_track:
        await interaction.followup.send("🧠 I'm still analyzing the vibe of this song. Try again in 5 seconds!")
        return

    # --- NEW: Unpack all 7 values returned by the updated get_seed_track ---
    seed_title, seed_url, target_v, target_a, seed_lang, seed_artist, seed_year = seed_track

    # 3. Fetch the 5 closest matches using the Advanced Weighted Algorithm
    recs = get_recommendations(target_v, target_a, seed_url, seed_lang, seed_artist, seed_year, limit=5)

    if not recs:
        await interaction.followup.send("I haven't learned enough similar songs yet to make a match!")
        return

    # 4. Build the Embed UI
    embed = discord.Embed(
        title="🎧 KaiROS Advanced Vibe Match",
        description=f"Based on: **{seed_title}**\n*(V: {target_v:.2f} | A: {target_a:.2f})*",
        color=discord.Color.gold()
    )

    urls_to_queue = []
    for i, rec in enumerate(recs, 1):
        # --- NEW: Unpack the 5 values returned by our new SQL query ---
        rec_title, rec_url, rec_v, rec_a, score = rec 
        urls_to_queue.append(rec_url)
        
        display_title = (rec_title[:50] + '...') if len(rec_title) > 53 else rec_title
        
        # We display the "Match Score" so users can see the AI's confidence!
        embed.add_field(
            name=f"{i}. {display_title}",
            value=f"[Listen]({rec_url}) | *Vibe: {rec_v:.2f}, {rec_a:.2f} | Score: {score:.3f}*",
            inline=False
        )

    # 5. The Callback Bridge to trigger playback
    async def trigger_playback(btn_interaction: discord.Interaction, url: str):
        await process_play_request(btn_interaction, url)

    # 6. Send with the specialized View
    view = RecommendView(urls=urls_to_queue, play_callback=trigger_playback)
    await interaction.followup.send(embed=embed, view=view)

# play
@bot.tree.command(name="play", description="Add a YouTube link to queue")
@app_commands.describe(url="YouTube link or song name")
async def play(interaction: discord.Interaction, url: str):
    # Pass off to the new shared helper!
    await process_play_request(interaction, url)

@bot.tree.command(name="start", description="Pick a vibe and let KaiROS choose the first song.")
async def start_session(interaction: discord.Interaction):
    
    # This is the "Bridge" function. The UI will pass the URL back here!
    async def trigger_playback(btn_interaction: discord.Interaction, url: str):
        # Pass the button interaction and the URL directly into your existing player logic!
        await process_play_request(btn_interaction, url)

    embed = discord.Embed(
        title="🎛️ Booting up KaiROS",
        description="How are we feeling today? Choose a starting vibe below:",
        color=discord.Color.blurple()
    )
    
    # Send the embed and attach the View, passing our bridge function to it
    await interaction.response.send_message(embed=embed, view=VibeSelector(play_callback=trigger_playback))

# run
if __name__ == "__main__":
    init_db()
    bot.run(TOKEN)