import yt_dlp
import asyncio
import logging
logger = logging.getLogger(__name__)
import os

from utils.ydl_config import get_download_opts
YDL_OPTIONS = get_download_opts()

async def download_track(video_url, pre_info=None):
    """Downloads a track. If pre_info is provided, attempts to skip re-extraction.
    
    Includes retry logic for transient failures (403, network glitches).
    """
    loop = asyncio.get_running_loop()

    def _dl():
        max_retries = 2
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    # Fast path: use pre-extracted info to skip re-extraction
                    if pre_info and attempt == 0:
                        try:
                            ydl.process_info(pre_info)
                            filename = ydl.prepare_filename(pre_info)
                            title = pre_info.get("title")
                            logger.info(f"⚡ Fast download (skipped re-extraction): {title}")
                            return filename, title, pre_info
                        except Exception as e:
                            logger.info(f"Pre-extracted info stale, re-extracting: {e}")

                    # Full extraction + download
                    info = ydl.extract_info(video_url, download=True)

                    if not info:
                        raise Exception("Video rejected by filter.")

                    filename = ydl.prepare_filename(info)
                    title = info.get("title")
                    return filename, title, info

            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)

                # Duration filter — don't retry, this is intentional
                if "This song file can't be fetched" in error_msg:
                    logger.warning(f"Skipped {video_url}: Exceeds 30 mins limit.")
                    return None, None, None

                last_error = e
                if attempt < max_retries:
                    wait = 1.5 * (attempt + 1)
                    logger.warning(f"Download attempt {attempt + 1} failed for {video_url}: {e}. Retrying in {wait}s...")
                    import time
                    time.sleep(wait)
                else:
                    logger.error(f"Download failed for {video_url} after {max_retries + 1} attempts: {e}")
                    raise last_error

    return await loop.run_in_executor(None, _dl)

# Ultra-fast search options (No downloading, just scraping titles)
from utils.ydl_config import get_search_opts
SEARCH_OPTIONS = get_search_opts()

async def fetch_search_results(query: str, limit: int = 5):
    """Fetches top N search results from YouTube without downloading."""
    loop = asyncio.get_running_loop()
    
    def _search():
        with yt_dlp.YoutubeDL(SEARCH_OPTIONS) as ydl:
            info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
            if info and "entries" in info:
                # We can also pre-filter search results here if YouTube provided duration!
                valid_entries = []
                for entry in info["entries"][:limit]:
                    duration = entry.get('duration')
                    # Keep it if duration is under 30 mins, or if duration is unknown
                    if not duration or duration <= 1800:
                        valid_entries.append(entry)
                return valid_entries
            return []
            
    try:
        return await loop.run_in_executor(None, _search)
    except Exception as e:
        logging.getLogger(__name__).error(f"Search failed for '{query}': {e}")
        return []