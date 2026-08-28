import asyncio
import logging
import random
import discord

from queuemgr.queue_state import QueueState
from queuemgr.playback import download_track
from queuemgr.lazydel import LazyDeleter
from queuemgr.autoplay_mgr import fill_autoplay
from queuemgr.processor import InferenceQueue

logger = logging.getLogger(__name__)

MAX_QUEUE_SIZE = 100
MAX_CONSECUTIVE_FAILURES = 3


class QueueManager:
    def __init__(self, bot, ffmpeg_options):
        self.bot = bot
        self.ffmpeg_options = ffmpeg_options
        self.state = QueueState()
        self.deleter = LazyDeleter(threshold=20)
        self.inference_queue = InferenceQueue(self.deleter)
        self._processing = set()
        self._consecutive_failures = {}  # guild_id -> int

    async def add(self, interaction, filename, title, video_url, full_info=None):
        gid = interaction.guild.id
        user_q = self.state.user_q(gid)
        auto_q = self.state.auto_q(gid)

        # Max queue size protection
        if len(user_q) + len(auto_q) >= MAX_QUEUE_SIZE:
            await interaction.channel.send(
                f"⚠️ Queue is full ({MAX_QUEUE_SIZE} tracks max). Skip or clear some tracks first."
            )
            return

        user_q.append((video_url, title, full_info or {}))
        vc = interaction.guild.voice_client

        if vc and not vc.is_playing() and gid not in self._processing:
            self.state.stopped.discard(gid)
            await self.play_next(interaction.guild, interaction.channel)

    async def play_next(self, guild, channel):
        gid = guild.id

        if gid in self.state.stopped:
            return

        vc = guild.voice_client
        crashed_track = None

        # ===================================================
        # 🛡️ THE DYNAMIC RECONNECT & CRASH RECOVERY SYSTEM
        # ===================================================
        if not vc or not vc.is_connected():
            logger.warning("Voice client disconnected. Waiting for auto-reconnect...")

            crashed_track = self.state.current_track.get(gid)

            attempts = 0
            while attempts < 20:
                vc = guild.voice_client
                if vc and vc.is_connected():
                    logger.info(f"✅ Reconnected in just {attempts * 0.5} seconds!")
                    break
                await asyncio.sleep(0.5)
                attempts += 1

            if not vc or not vc.is_connected():
                logger.error(f"Voice client failed to recover after 10s. Halting.")
                self.clear(gid)
                self.deleter.force_gc()
                if gid in self._processing:
                    self._processing.discard(gid)
                return
        # ===================================================

        self._processing.add(gid)

        try:
            user_q = self.state.user_q(gid)
            auto_q = self.state.auto_q(gid)

            # ===================================================
            # 🔄 RECOVERY INJECTION
            # ===================================================
            if crashed_track:
                old_fname = crashed_track[0]
                old_title = crashed_track[1]
                old_url = crashed_track[2]
                old_info = crashed_track[3] if len(crashed_track) > 3 else {}

                user_q.insert(0, (old_url, old_title, old_info))
                await channel.send(f"🔌 **Network hiccup recovered!** Restarting: **{old_title}**")

            # 1. Figure out what to play next
            is_autoplay = False
            if user_q:
                q_item = user_q.pop(0)
            else:
                if not auto_q:
                    await fill_autoplay(self.state, gid)

                if not auto_q:
                    self._processing.discard(gid)
                    return
                q_item = auto_q.pop(0)
                is_autoplay = True

            url = q_item[0]
            title = q_item[1]
            full_info = q_item[2] if len(q_item) > 2 else {}

            # 2. Download the track (pass pre_info to skip double extraction)
            filename, title, fresh_info = await download_track(url, pre_info=full_info if full_info else None)

            if filename is None:
                await channel.send("⏱️ This track can't be fetched — it may be too long, region-locked, or unavailable.")
                self._processing.discard(gid)

                # Track consecutive failures to prevent infinite loops
                fails = self._consecutive_failures.get(gid, 0) + 1
                self._consecutive_failures[gid] = fails

                if fails >= MAX_CONSECUTIVE_FAILURES:
                    self._consecutive_failures[gid] = 0
                    await channel.send("⚠️ Multiple tracks failed in a row. Pausing autoplay — try `/play` with a direct link.")
                    return

                asyncio.create_task(self.play_next(guild, channel))
                return

            if not full_info:
                full_info = fresh_info

            # Reset failure counter on success
            self._consecutive_failures[gid] = 0

            # 3. Handle old file cleanup
            old_track = self.state.current_track.get(gid)
            if old_track:
                old_fname = old_track[0]
                old_title = old_track[1]
                old_url = old_track[2]
                old_info = old_track[3] if len(old_track) > 3 else {}

                old_info['title'] = old_title
                old_info['url'] = old_url

                self.inference_queue.enqueue(old_fname, old_info, gid)

            # 4. Update state with the NEW track
            self.state.current_track[gid] = (filename, title, url, full_info)
            self.state.history_set(gid).add(url)
            logger.info(f"Playing {title}")

            # 5. Define the callback for when the song finishes
            def after_play(err):
                if err:
                    logger.error(f"Player error: {err}")

                if gid not in self.state.stopped:
                    # Check loop mode
                    loop_mode = self.state.loop_mode.get(gid, "off")

                    if loop_mode == "track":
                        # Re-insert current track at front of user queue
                        self.state.user_q(gid).insert(0, (url, title, full_info))

                    elif loop_mode == "queue":
                        # Append current track to end of user queue
                        self.state.user_q(gid).append((url, title, full_info))

                    asyncio.run_coroutine_threadsafe(
                        self.play_next(guild, channel),
                        self.bot.loop
                    )

            # 6. Start playing
            vc.play(
                discord.FFmpegPCMAudio(filename, **self.ffmpeg_options),
                after=after_play
            )

            self._processing.discard(gid)

            # Rich now-playing embed
            source_tag = "🤖 Autoplay" if is_autoplay else "🎵 Queued"
            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"**[{title}]({url})**",
                color=0x7C3AED
            )

            # Add thumbnail if available
            thumb = (full_info or {}).get("thumbnail")
            if thumb:
                embed.set_thumbnail(url=thumb)

            # Duration
            duration = (full_info or {}).get("duration")
            if duration:
                mins, secs = divmod(int(duration), 60)
                embed.add_field(name="Duration", value=f"{mins}:{secs:02d}", inline=True)

            # Artist
            artist = (full_info or {}).get("artist") or (full_info or {}).get("creator") or (full_info or {}).get("uploader")
            if artist:
                embed.add_field(name="Artist", value=artist, inline=True)

            embed.add_field(name="Source", value=source_tag, inline=True)

            # Queue info
            remaining = len(user_q) + len(auto_q)
            if remaining > 0:
                embed.set_footer(text=f"{remaining} track{'s' if remaining != 1 else ''} in queue")

            await channel.send(embed=embed)
            self.bot.loop.create_task(self.prefetch_next(guild))

            # 7. Pre-fill autoplay in the background for the NEXT round
            if not user_q and len(auto_q) < 6:
                asyncio.create_task(fill_autoplay(self.state, gid))

        except Exception as e:
            logger.error(f"Error in play_next: {e}")
            self._processing.discard(gid)

            # Track consecutive failures to prevent infinite loops
            fails = self._consecutive_failures.get(gid, 0) + 1
            self._consecutive_failures[gid] = fails

            if fails >= MAX_CONSECUTIVE_FAILURES:
                self._consecutive_failures[gid] = 0
                await channel.send("⚠️ Multiple tracks failed in a row. Pausing autoplay — try `/play` with a direct link.")
                return

            asyncio.create_task(self.play_next(guild, channel))

    async def prefetch_next(self, guild):
        """Looks ahead in the queue and downloads the next track in the background."""
        await asyncio.sleep(5)

        gid = guild.id
        user_q = self.state.user_q(gid)
        auto_q = self.state.auto_q(gid)

        # Snapshot the next URL before acting
        next_item = None
        if user_q:
            next_item = user_q[0]
        elif auto_q:
            next_item = auto_q[0]

        if next_item:
            next_url = next_item[0]
            next_info = next_item[2] if len(next_item) > 2 else None

            # Verify it's still the next track (queue might have changed)
            current_next = (user_q[0] if user_q else auto_q[0] if auto_q else None)
            if current_next and current_next[0] == next_url:
                logger.info("💿 Pre-fetching next track for seamless playback...")
                try:
                    await download_track(next_url, pre_info=next_info if next_info else None)
                except Exception as e:
                    logger.error(f"❌ Failed to pre-fetch track: {e}")

    def skip(self, gid):
        vc = self.bot.get_guild(gid).voice_client
        if vc and vc.is_playing():
            vc.stop()

    def clear(self, gid):
        self.state.stopped.add(gid)
        guild = self.bot.get_guild(gid)

        if guild and guild.voice_client:
            guild.voice_client.stop()

        self.state.user_q(gid).clear()
        self.state.auto_q(gid).clear()

        track = self.state.current_track.pop(gid, None)
        if track:
            self.deleter.enqueue(track)

    def clear_queue(self, gid):
        """Clears the queue WITHOUT stopping the current track."""
        self.state.user_q(gid).clear()
        self.state.auto_q(gid).clear()

    def shuffle(self, gid):
        """Shuffles the user queue."""
        q = self.state.user_q(gid)
        if q:
            random.shuffle(q)

    def remove(self, gid, index):
        """Removes a track at the given 1-based index from the combined queue.
        Returns the removed title, or None if index is invalid."""
        user_q = self.state.user_q(gid)
        auto_q = self.state.auto_q(gid)

        # Convert 1-based to 0-based
        idx = index - 1

        if idx < 0:
            return None

        if idx < len(user_q):
            removed = user_q.pop(idx)
            return removed[1]
        else:
            auto_idx = idx - len(user_q)
            if auto_idx < len(auto_q):
                removed = auto_q.pop(auto_idx)
                return removed[1]

        return None

    def move(self, gid, from_pos, to_pos):
        """Moves a track from one 1-based position to another in the user queue.
        Returns the moved title, or None if positions are invalid."""
        q = self.state.user_q(gid)
        from_idx = from_pos - 1
        to_idx = to_pos - 1

        if from_idx < 0 or from_idx >= len(q) or to_idx < 0 or to_idx >= len(q):
            return None

        item = q.pop(from_idx)
        q.insert(to_idx, item)
        return item[1]

    def get_queue_snapshot(self, guild_id):
        track = self.state.current_track.get(guild_id)

        # Return richer data: (title, source_tag) tuples
        user_items = [(item[1], "🎵") for item in self.state.user_q(guild_id)]
        auto_items = [(item[1], "🤖") for item in self.state.auto_q(guild_id)]
        queue_data = user_items + auto_items

        return track, queue_data