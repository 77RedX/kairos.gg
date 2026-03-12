import os
import threading
import time
import logging

logger = logging.getLogger(__name__)

class LazyDeleter:
    def __init__(self, threshold=20):
        self.DELETE_THRESHOLD = threshold
        self.delete_queue = set()
        self.gc_running = False
        self.lock = threading.Lock()

    def enqueue(self, track_info):
        """Expects a tuple: (filename, title, url)"""
        if not track_info or not track_info[0]:
            return

        with self.lock:
            # Add the entire tuple to the set
            self.delete_queue.add(track_info)
            if len(self.delete_queue) >= self.DELETE_THRESHOLD:
                self._start_gc()

    def force_gc(self):
        self._start_gc()

    def _start_gc(self):
        if self.gc_running:
            return

        self.gc_running = True
        threading.Thread(target=self._gc_loop, daemon=True).start()

    def _gc_loop(self):
        try:
            while True:
                with self.lock:
                    if not self.delete_queue:
                        break
                    # Convert set of tuples to a list to iterate over safely
                    items = list(self.delete_queue)

                deleted_any = False

                for item in items:
                    filename, title, url = item
                    
                    try:
                        # ==========================================
                        # 🧠 ML PROCESSING PIPELINE (FUTURE UPGRADE)
                        # ==========================================
                        # 1. Check if 'url' exists in your SQLite DB.
                        # 2. If not, analyze 'filename' to get Valence/Arousal.
                        # 3. Save (url, title, valence, arousal) to DB.
                        # logger.info(f"Analyzed {title}: V=0.58, A=0.74")
                        # ==========================================

                        if os.path.exists(filename):
                            os.remove(filename)
                            logger.info(f"GC processed and deleted: {filename}")

                        with self.lock:
                            self.delete_queue.discard(item)

                        deleted_any = True

                    except PermissionError:
                        # FFmpeg still holding the file, we will try again next loop
                        continue

                    except Exception as e:
                        logger.warning(f"GC error processing/deleting {filename}: {e}")
                        with self.lock:
                            self.delete_queue.discard(item)

                if not deleted_any:
                    time.sleep(1)

                with self.lock:
                    if not self.delete_queue: 
                        break
        finally:
            self.gc_running = False