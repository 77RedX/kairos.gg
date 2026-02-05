import os
import asyncio
import logging
import discord
from queuemgr.lazydel import LazyDeleter

logger = logging.getLogger(__name__)

class QueueManager:
    def __init__(self, bot, ffmpeg_options):
        self.bot = bot
        self.ffmpeg_options = ffmpeg_options
        self.queues = {}          # guild_id -> [(filename, title)]
        self.current_track = {}  # guild_id -> (filename, title)
        #self.current_file = {}    # guild_id -> filename
        self.stopped = set()      # guilds manually stopped
        self.deleter = LazyDeleter(threshold=20) # delete queue

    def get_queue(self, guild_id):
        return self.queues.setdefault(guild_id, [])

    async def add(self, interaction, filename, title):
        guild_id = interaction.guild.id
        queue = self.get_queue(guild_id)
        queue.append((filename, title))

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

        queue = self.get_queue(guild_id)
        vc = guild.voice_client

        if not vc or not queue:
            self.current_track.pop(guild_id, None)
            return

        filename, title = queue.pop(0)
        self.current_track[guild_id] = (filename, title)

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

    def get_queue_snapshot(self, guild_id):
        """
        Returns:
            current_title (str | None)
            queue_titles (list[str])
        """
        track = self.current_track.get(guild_id)
        current_title = track[1] if track else None

        queue_titles = [title for _, title in self.get_queue(guild_id)]
        return current_title, queue_titles

    def skip(self, guild_id):
        vc = self.bot.get_guild(guild_id).voice_client
        if vc and vc.is_playing():
            vc.stop()

    def clear(self, guild_id):
        self.stopped.add(guild_id)

        guild = self.bot.get_guild(guild_id)
        if guild and guild.voice_client:
            guild.voice_client.stop()

        queue = self.get_queue(guild_id)
        for filename, _ in queue:
            self._safe_delete(filename)

        queue.clear()
        self._delete_file(guild_id)

    def _delete_file(self, guild_id):
        track = self.current_track.pop(guild_id, None)
        if track:
            filename, _ = track
            self._safe_delete(filename)

    def _safe_delete(self, filename):
        if filename:
            self.deleter.enqueue(filename)