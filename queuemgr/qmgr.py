import asyncio
import logging
import discord

from queuemgr.queue_state import QueueState
from queuemgr.playback import download_track
from queuemgr.lazydel import LazyDeleter
from queuemgr.autoplay_mgr import fill_autoplay
from queuemgr.processor import InferenceQueue

logger = logging.getLogger(__name__)

class QueueManager:
    def __init__(self, bot, ffmpeg_options):
        self.bot = bot
        self.ffmpeg_options = ffmpeg_options
        self.state = QueueState()
        self.deleter = LazyDeleter(threshold=20)
        self.inference_queue = InferenceQueue(self.deleter)
        self._processing = set() 

    # --- NEW: Added full_info as a parameter ---
    async def add(self, interaction, filename, title, video_url, full_info=None):
        gid = interaction.guild.id
        # --- NEW: Append full_info to the queue tuple (fallback to empty dict if None) ---
        self.state.user_q(gid).append((video_url, title, full_info or {}))
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
                # --- NEW: Safely unpack variable-length tuple ---
                old_fname = crashed_track[0]
                old_title = crashed_track[1]
                old_url = crashed_track[2]
                old_info = crashed_track[3] if len(crashed_track) > 3 else {}
                
                user_q.insert(0, (old_url, old_title, old_info))
                await channel.send(f"🔌 **Network hiccup recovered!** Restarting: **{old_title}**")

            # 1. Figure out what to play next
            if user_q:
                # --- NEW: Unpack the 3-item tuple safely ---
                q_item = user_q.pop(0)
            else:
                if not auto_q:
                    await fill_autoplay(self.state, gid)
                
                if not auto_q:
                    self._processing.discard(gid) 
                    return
                # --- NEW: Unpack the 3-item tuple safely ---
                q_item = auto_q.pop(0)

            # --- NEW: Ensure url, title, and full_info are safely extracted ---
            url = q_item[0]
            title = q_item[1]
            full_info = q_item[2] if len(q_item) > 2 else {}

            # 2. Download the track
            filename, title, fresh_info = await download_track(url)
            
            if filename is None:
                await channel.send("❌ This song file can't be fetched.")
                self._processing.discard(gid)
                asyncio.create_task(self.play_next(guild, channel))
                return
            
            if not full_info:
                full_info = fresh_info

            # 3. Handle old file cleanup
            old_track = self.state.current_track.get(gid)
            if old_track:
                # --- NEW: Unpack the 4-item tuple from current_track ---
                old_fname = old_track[0]
                old_title = old_track[1]
                old_url = old_track[2]
                old_info = old_track[3] if len(old_track) > 3 else {}
                
                # --- NEW: Make sure title and URL are guaranteed to exist in the dict ---
                old_info['title'] = old_title
                old_info['url'] = old_url
                
                # Send the entire dictionary to processing!
                self.inference_queue.enqueue(old_fname, old_info, gid)

            # 4. Update state with the NEW track
            # --- NEW: Save full_info into the current_track state ---
            self.state.current_track[gid] = (filename, title, url, full_info)
            self.state.history_set(gid).add(url)
            logger.info(f"Playing {title}")

            # 5. Define the callback for when the song finishes
            def after_play(err):
                if err:
                    logger.error(f"Player error: {err}")
                
                if gid not in self.state.stopped:
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
            
            await channel.send(f"🎵 Now playing: **{title}**")
            self.bot.loop.create_task(self.prefetch_next(guild))

            # 7. Pre-fill autoplay in the background for the NEXT round
            if not user_q and len(auto_q) < 6: 
                asyncio.create_task(fill_autoplay(self.state, gid))

        except Exception as e:
            logger.error(f"Error in play_next: {e}")
            self._processing.discard(gid)
            asyncio.create_task(self.play_next(guild, channel))
    
    async def prefetch_next(self, guild):
        """Looks ahead in the queue and downloads the next track in the background."""
        await asyncio.sleep(5) 
        
        gid = guild.id
        user_q = self.state.user_q(gid)
        auto_q = self.state.auto_q(gid)
        
        next_url = None
        if user_q:
            next_url = user_q[0][0]
        elif auto_q:
            next_url = auto_q[0][0]
            
        if next_url:
            logger.info("💿 Pre-fetching next track for seamless playback...")
            try:
                await download_track(next_url)
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

    def get_queue_snapshot(self, guild_id):
        track = self.state.current_track.get(guild_id) 

        # --- NEW: Safely extract titles regardless of tuple length ---
        queue_titles = (
            [item[1] for item in self.state.user_q(guild_id)] +
            [item[1] for item in self.state.auto_q(guild_id)]
        )
        return track, queue_titles