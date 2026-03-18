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
        # NEW: A lock to prevent multiple songs from trying to play at the exact same time
        self._processing = set() 

    async def add(self, interaction, filename, title, video_url):
        gid = interaction.guild.id
        self.state.user_q(gid).append((video_url, title))
        vc = interaction.guild.voice_client

        # Check if we are already playing OR actively processing a download
        if vc and not vc.is_playing() and gid not in self._processing:
            self.state.stopped.discard(gid)
            await self.play_next(interaction.guild, interaction.channel)

    async def play_next(self, guild, channel):
        gid = guild.id

        if gid in self.state.stopped:
            return

        vc = guild.voice_client
        if not vc or not vc.is_connected():
            logger.info(f"Voice client dead or disconnected. Halting play_next.")
            # Clear the queue so the domino effect stops instantly
            self.clear(gid)
            self.deleter.force_gc()
            
            # Make sure we unlock the processing state before we leave
            if gid in self._processing:
                self._processing.discard(gid)
            return

        # Lock the queue so other commands don't interrupt the download process
        self._processing.add(gid)

        try:
            user_q = self.state.user_q(gid)
            auto_q = self.state.auto_q(gid)

            # 1. Figure out what to play next
            if user_q:
                url, title = user_q.pop(0)
            else:
                if not auto_q:
                    # Await autoplay filling since we actually need a song NOW
                    await fill_autoplay(self.state, gid)
                
                if not auto_q:
                    self._processing.discard(gid) # Unlock before returning
                    return
                url, title = auto_q.pop(0)

            # 2. Download the track
            filename, title = await download_track(url)

            # 3. Handle old file cleanup
            old_track = self.state.current_track.get(gid)
            if old_track:
                # FIX: Use 'old_' prefix so we don't overwrite the newly downloaded song variables!
                old_fname, old_title, old_url = old_track
                song_info = {"title": old_title, "url": old_url}
                # Send to processing first!
                self.inference_queue.enqueue(old_fname, song_info, gid)

            # 4. Update state with the NEW track
            self.state.current_track[gid] = (filename, title, url)
            self.state.history_set(gid).add(url)
            logger.info(f"Playing {title}")

            # 5. Define the callback for when the song finishes
            def after_play(err):
                if err:
                    logger.error(f"Player error: {err}")
                
                if gid not in self.state.stopped:
                    # Trigger the next song
                    asyncio.run_coroutine_threadsafe(
                        self.play_next(guild, channel),
                        self.bot.loop
                    )

            # 6. Start playing
            vc.play(
                discord.FFmpegPCMAudio(filename, **self.ffmpeg_options),
                after=after_play
            )
            
            # Unlock now that the audio is actively playing
            self._processing.discard(gid)
            
            await channel.send(f"🎵 Now playing: **{title}**")
            self.bot.loop.create_task(self.prefetch_next(guild))

            # 7. Pre-fill autoplay in the background for the NEXT round
            if not user_q and len(auto_q) < 6: 
                asyncio.create_task(fill_autoplay(self.state, gid))

        except Exception as e:
            logger.error(f"Error in play_next: {e}")
            self._processing.discard(gid)
            # Try to force the next song if this one crashed
            asyncio.create_task(self.play_next(guild, channel))
    
    async def prefetch_next(self, guild):
        """Looks ahead in the queue and downloads the next track in the background."""
        # Give the autoplay manager a couple of seconds to fetch related 
        # YouTube links if the queue just emptied out.
        await asyncio.sleep(5) 
        
        gid = guild.id
        user_q = self.state.user_q(gid)
        auto_q = self.state.auto_q(gid)
        
        # Peek at the next URL without popping it off the list
        next_url = None
        if user_q:
            next_url = user_q[0][0]
        elif auto_q:
            next_url = auto_q[0][0]
            
        if next_url:
            logger.info("💿 Pre-fetching next track for seamless playback...")
            try:
                # This downloads the file and caches it in your downloads/ folder.
                # When play_next() eventually asks for it, it will load instantly!
                await download_track(next_url)
            except Exception as e:
                logger.error(f"❌ Failed to pre-fetch track: {e}")

    def skip(self, gid):
        vc = self.bot.get_guild(gid).voice_client
        if vc and vc.is_playing():
            vc.stop() # This naturally triggers after_play, advancing the queue!

    def clear(self, gid):
        self.state.stopped.add(gid)
        guild = self.bot.get_guild(gid)
        
        if guild and guild.voice_client:
            guild.voice_client.stop()

        self.state.user_q(gid).clear()
        self.state.auto_q(gid).clear()

        # Clean up the currently playing file immediately
        track = self.state.current_track.pop(gid, None)
        if track:
            self.deleter.enqueue(track)

    def get_queue_snapshot(self, guild_id):
        # This is the (filename, title, url) tuple
        track = self.state.current_track.get(guild_id) 

        # We return the whole track tuple for 'current', not just the title
        queue_titles = (
            [title for _, title in self.state.user_q(guild_id)] +
            [title for _, title in self.state.auto_q(guild_id)]
        )
        return track, queue_titles