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
        """Expects a tuple (filename, title, url, ...) OR just a filename string"""
        if not track_info:
            return

        # --- FIX: Extract ONLY the filename string right away ---
        if isinstance(track_info, (list, tuple)):
            filename = track_info[0]
        else:
            filename = track_info

        with self.lock:
            # Now we are only adding a pure string to the set! No more hash errors.
            self.delete_queue.add(filename)
            if len(self.delete_queue) >= self.DELETE_THRESHOLD:
                self._start_gc()

    def force_gc(self):
        self._start_gc()

    def _start_gc(self):
        with self.lock:
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
                    items = list(self.delete_queue)

                deleted_any = False

                for item in items:
                    # --- FIX: Safely unpack based on type ---
                    if isinstance(item, (list, tuple)):
                        filename = item[0]
                    else:
                        filename = item
                    # ----------------------------------------
                    
                    try:
                        if os.path.exists(filename):
                            os.remove(filename)
                            logger.info(f"🗑️ GC processed and deleted: {filename}")

                        with self.lock:
                            self.delete_queue.discard(item)

                        deleted_any = True

                    except PermissionError:
                        # FFmpeg still holding the file, try again next loop
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