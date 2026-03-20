import yt_dlp
import asyncio
import os
import logging

logger = logging.getLogger(__name__)

if os.name == 'posix':
    _tmpl = "/dev/shm/kairos_%(id)s.%(ext)s"
else:
    _tmpl = "downloads/%(id)s.%(ext)s"

_js_config = {"node": {}}

def filter_duration(info, *, incomplete):
    duration = info.get('duration')
    if duration and duration > 1800: # 1800 seconds = 30 minutes
        return 'This song file can\'t be fetched. (Duration > 30 mins)'
    return None

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "outtmpl": _tmpl,
    "quiet": True,
    "js_runtimes": _js_config,
    "concurrent_fragment_downloads": 10,
    "http_chunk_size": 10485760,
    "source_address": "0.0.0.0",
    "match_filter": filter_duration, # <-- Added the filter here
}

async def download_track(video_url):
    loop = asyncio.get_running_loop()

    def _dl():
        try:
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(video_url, download=True)
                
                # Check if the download was skipped by the filter
                if not info:
                    raise Exception("Video rejected by filter.")
                
                filename = ydl.prepare_filename(info)
                title = info.get("title")
                return filename, title, info
        except yt_dlp.utils.DownloadError as e:
            # Check if it was our specific duration error
            if "This song file can't be fetched" in str(e):
                logger.warning(f"Skipped {video_url}: Exceeds 30 mins limit.")
                return None, None, None
            # Otherwise, re-raise the actual error (like copyright or network issues)
            logger.error(f"Download failed for {video_url}: {e}")
            raise e

    return await loop.run_in_executor(None, _dl)

# Ultra-fast search options (No downloading, just scraping titles)
SEARCH_OPTIONS = {
    "format": "bestaudio/best",
    "extract_flat": True, 
    "quiet": True,
    "noplaylist": True,
    "no_warnings": True,
    "ignoreerrors": True,
    "js_runtimes": _js_config,
}

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