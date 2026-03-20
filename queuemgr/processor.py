import asyncio
import logging
from autoplay.inference import EmotionAnalyzer
from database.database import log_track_emotion, check_if_exists
# IMPORT OUR NEW DETECTOR
from utils.language_utils import TitleLanguageDetector 

logger = logging.getLogger(__name__)

class InferenceQueue:
    def __init__(self, lazy_deleter):
        self.queue = asyncio.Queue()
        self.deleter = lazy_deleter
        self.analyzer = EmotionAnalyzer()
        self.lang_detector = TitleLanguageDetector() # Initialize the detector
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
                    # 2. Extract Metadata & Detect Language
                    title = song_info.get('title', 'Unknown Title')
                    artist = song_info.get('artist') or song_info.get('creator') or song_info.get('uploader', 'unknown')
                    duration = song_info.get('duration', 0)
                    raw_year = song_info.get('release_year') or (song_info.get('upload_date', '0000')[:4] if song_info.get('upload_date') else '0')
                    year = int(raw_year) if raw_year else 0
                    
                    # RUN OUR REGEX + AI LANGUAGE DETECTOR
                    detected_language = await asyncio.to_thread(self.lang_detector.detect, title)

                    # 3. If it's a new song, run the heavy librosa/PyTorch math
                    logger.info(f"🧠 Processing Emotion for: {title}")
                    result = await asyncio.to_thread(self.analyzer.analyze_audio, file_path)
                    
                    if result:
                        v_avg, a_avg = result['v_avg'], result['a_avg']
                        v_std, a_std = result['v_std'], result['a_std']
                        
                        logger.info(f"📊 Result for '{title}': V_avg={v_avg:.2f}, A_avg={a_avg:.2f}")
                        
                        # 4. Log everything to the DB
                        await asyncio.to_thread(
                            log_track_emotion, 
                            guild_id, 
                            title, 
                            song_info['url'], 
                            v_avg, a_avg, v_std, a_std,
                            language=detected_language,  # <-- Pass the detected language
                            artist=artist,               # <-- Pass the extracted artist
                            duration=duration,           # <-- Pass duration
                            year=int(year)               # <-- Pass year
                        )
                    
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
            
            finally:
                self.deleter.enqueue(file_path)
                self.queue.task_done()