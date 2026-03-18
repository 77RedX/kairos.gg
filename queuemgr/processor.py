import asyncio
import logging
from autoplay.inference import EmotionAnalyzer
from database.database import log_track_emotion, check_if_exists

logger = logging.getLogger(__name__)

class InferenceQueue:
    def __init__(self, lazy_deleter):
        self.queue = asyncio.Queue()
        self.deleter = lazy_deleter
        self.analyzer = EmotionAnalyzer()
        self._task = None

    def start(self):
        """Starts the background worker."""
        if not self._task:
            self._task = asyncio.create_task(self._worker())

    def enqueue(self, file_path, song_info, guild_id):
        """Adds a finished song to the processing queue."""
        self.queue.put_nowait((file_path, song_info, guild_id))
        logger.info(f"Added to processing queue: {file_path}")

    async def _worker(self):
        """Continuously pulls files, processes them, and deletes them."""
        await asyncio.sleep(5) 
        
        while True:
            file_path, song_info, guild_id = await self.queue.get() 
            
            try:
                # 1. NEW CHECK: Does this URL already exist in the database?
                already_analyzed = await asyncio.to_thread(check_if_exists, song_info['url'])
                
                if already_analyzed:
                    logger.info(f"⏭️ Skipping ML math; '{song_info['title']}' is already in DB.")
                
                else:
                    # 2. If it's a new song, run the heavy librosa/PyTorch math
                    logger.info(f"🧠 Processing Emotion for: {song_info['title']}")
                    result = await asyncio.to_thread(self.analyzer.analyze_audio, file_path)
                    
                    if result:
                    # Unpack the new four values
                        v_avg, a_avg = result['v_avg'], result['a_avg']
                        v_std, a_std = result['v_std'], result['a_std']
                        
                        logger.info(f"📊 Result for '{song_info['title']}': V_avg={v_avg:.2f} (±{v_std:.2f}), A_avg={a_avg:.2f} (±{a_std:.2f})")
                        
                        await asyncio.to_thread(
                            log_track_emotion, 
                            guild_id, 
                            song_info['title'], 
                            song_info['url'], 
                            v_avg, a_avg, v_std, a_std
                        )
                    
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
            
            finally:
                self.deleter.enqueue(file_path)
                self.queue.task_done()