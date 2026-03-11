import os
import asyncio
import logging
import discord
from queuemgr.lazydel import LazyDeleter
from autoplay.recommender import get_related, _normalize_title

logger = logging.getLogger(__name__)


class QueueManager:

    def __init__(self, bot, ffmpeg_options):
        self.bot = bot
        self.ffmpeg_options = ffmpeg_options

        # two queue system
        self.user_queues = {}
        self.auto_queues = {}
        self.history = {}  # guild_id -> set(video_urls)
        self.current_track = {}

        self.stopped = set()

        self.deleter = LazyDeleter(threshold=20)

        # prevents multiple autoplay tasks
        self.autoplay_lock = set()

    def get_history(self, guild_id):
        return self.history.setdefault(guild_id, set())

    def get_user_queue(self, guild_id):
        return self.user_queues.setdefault(guild_id, [])

    def get_auto_queue(self, guild_id):
        return self.auto_queues.setdefault(guild_id, [])

    async def add(self, interaction, filename, title, video_url):

        guild_id = interaction.guild.id

        queue = self.get_user_queue(guild_id)
        queue.append((filename, title, video_url))
        logger.info(f"User added: {title}")
        vc = interaction.guild.voice_client

        if not vc or not vc.is_playing():

            self.stopped.discard(guild_id)

            await self.play_next(interaction.guild, interaction.channel)

        else:

            await interaction.followup.send(f"➕ Added to queue: **{title}**")

    async def play_next(self, guild, channel):

        guild_id = guild.id

        if guild_id in self.stopped:
            return

        vc = guild.voice_client

        if not vc:
            return

        user_q = self.get_user_queue(guild_id)
        auto_q = self.get_auto_queue(guild_id)

        if user_q:

            filename, title, video_url = user_q.pop(0)

        elif auto_q:

            filename, title, video_url = auto_q.pop(0)

        else:

            await self._maybe_fill_autoplay(guild_id)

            auto_q = self.get_auto_queue(guild_id)

            if auto_q:
                filename, title, video_url = auto_q.pop(0)
                logger.info(f"Autoplay started: {title}")
            else:
                return

        self.current_track[guild_id] = (filename, title, video_url)
        logger.info(f"Starting track: {title}")
        history = self.get_history(guild_id)
        history.add(video_url)

        if len(history) > 30:
            history.pop()
        asyncio.create_task(self._maybe_fill_autoplay(guild_id))

        def after_play(error):

            if error:
                logger.error(f"Playback error: {error}")

            self._delete_file(guild_id)

            if guild_id not in self.stopped:

                asyncio.run_coroutine_threadsafe(
                    self.play_next(guild, channel),
                    self.bot.loop
                )

        vc.play(
            discord.FFmpegPCMAudio(filename, **self.ffmpeg_options),
            after=after_play
        )

        asyncio.create_task(
            channel.send(f"🎵 Now playing: **{title}**")
        )

    async def _maybe_fill_autoplay(self, guild_id):

        if guild_id in self.autoplay_lock:
            return

        self.autoplay_lock.add(guild_id)

        try:

            if guild_id in self.stopped:
                return

            user_q = self.get_user_queue(guild_id)
            auto_q = self.get_auto_queue(guild_id)

            if len(auto_q) >= 5:
                return
            
            track = self.current_track.get(guild_id)

            if not track:
                return

            filename, title, video_url = track

            # only generate when user queue low
            if len(user_q) > 1:
                return

            loop = asyncio.get_running_loop()

            def fetch():

                return get_related(title)

            history = self.get_history(guild_id)

            url = None
            
            curr_norm = _normalize_title(title)

            for _ in range(5):  # try up to 5 times

                candidate = await loop.run_in_executor(None, fetch)

                if not candidate:
                    break
                
                candidate_url, candidate_title = candidate
                
                cand_norm = _normalize_title(candidate_title)
                

                if candidate_url not in history and cand_norm != curr_norm:
                    url = candidate_url
                    break

            if not url:
                return

            import yt_dlp

            def extract():

                with yt_dlp.YoutubeDL({
                    "format": "bestaudio/best",
                    "outtmpl": "downloads/%(id)s.%(ext)s",
                    "quiet": True,
                }) as ydl:

                    info = ydl.extract_info(url, download=True)

                    filename = ydl.prepare_filename(info)
                    title = info.get("title", "Unknown")
                    video_url = info.get("webpage_url")
                    return filename, title, video_url

            await asyncio.sleep(0)

            result = await loop.run_in_executor(None, extract)

            if result and len(auto_q)<5 and len(user_q)<=1:
                auto_q.append(result)
                logger.info(f"Autoplay added: {result[1]}")

        finally:

            self.autoplay_lock.discard(guild_id)

    def get_queue_snapshot(self, guild_id):

        track = self.current_track.get(guild_id)

        current_title = track[1] if track else None

        queue_titles = (

            [title for _, title, _ in self.get_user_queue(guild_id)] +

            [title for _, title, _ in self.get_auto_queue(guild_id)]

        )

        return current_title, queue_titles

    def skip(self, guild_id):

        vc = self.bot.get_guild(guild_id).voice_client

        if vc and vc.is_playing():
            logger.info(f"Track skipped in guild {guild_id}")
            vc.stop()

    def clear(self, guild_id):

        self.stopped.add(guild_id)

        guild = self.bot.get_guild(guild_id)

        if guild and guild.voice_client:
            guild.voice_client.stop()

        user_q = self.get_user_queue(guild_id)
        auto_q = self.get_auto_queue(guild_id)

        for filename, _, _ in user_q:
            self._safe_delete(filename)

        for filename, _, _ in auto_q:
            self._safe_delete(filename)

        user_q.clear()
        auto_q.clear()

        self.history.pop(guild_id, None)
        self._delete_file(guild_id)

    def _delete_file(self, guild_id):

        track = self.current_track.pop(guild_id, None)

        if track:

            filename, _, _ = track

            self._safe_delete(filename)

    def _safe_delete(self, filename):

        if filename:

            self.deleter.enqueue(filename)