import os
import threading
import time
import logging

logger = logging.getLogger(__name__)

class LazyDeleter:
    def __init__(self, threshold=50):
        self.DELETE_THRESHOLD = threshold
        self.delete_queue = set()
        self.gc_running = False
        self.lock = threading.Lock()

    def enqueue(self, filename):
        if not filename:
            return

        with self.lock:
            self.delete_queue.add(filename)

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

                    filenames = list(self.delete_queue)

                deleted_any = False

                for filename in filenames:
                    try:
                        if os.path.exists(filename):
                            os.remove(filename)
                            logger.info(f"GC deleted: {filename}")

                        with self.lock:
                            self.delete_queue.discard(filename)

                        deleted_any = True

                    except PermissionError:
                        # FFmpeg still holding the file
                        continue

                    except Exception as e:
                        logger.warning(f"GC error deleting {filename}: {e}")
                        with self.lock:
                            self.delete_queue.discard(filename)

                if not deleted_any:
                    time.sleep(1)

                with self.lock:
                    if len(self.delete_queue) < self.DELETE_THRESHOLD:
                        break
        finally:
            self.gc_running = False