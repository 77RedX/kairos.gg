import yt_dlp
import asyncio
import logging
logger = logging.getLogger(__name__)

import os as _os

if _os.name == 'posix':
    _tmpl = "/dev/shm/kairos_%(id)s.%(ext)s"
    _JS_RUNTIME = {"quickjs": {"path": _os.path.expanduser("~/bin/qjs")}}
else:
    _tmpl = "downloads/%(id)s.%(ext)s"
    import shutil as _shutil
    _node = _shutil.which("node")
    _JS_RUNTIME = {"node": {"path": _node}} if _node else {"node": {}}

_COOKIES = _os.path.expanduser("~/kairos.gg/cookies.txt")

def filter_duration(info, *, incomplete):
    duration = info.get('duration')
    if duration and duration > 1800:
        return 'This song file can\'t be fetched. (Duration > 30 mins)'
    return None

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "outtmpl": _tmpl,
    "quiet": True,
    "no_warnings": True,
    "nocheckcertificate": True,
    "source_address": "0.0.0.0",
    "concurrent_fragment_downloads": 10,
    "http_chunk_size": 10485760,
    "match_filter": filter_duration,
    "js_runtimes": _JS_RUNTIME,
    **( {"cookiefile": _COOKIES} if _os.path.exists(_COOKIES) else {} ),
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
    "nocheckcertificate": True,
    "source_address": "0.0.0.0",
    "js_runtimes": _JS_RUNTIME,
    **( {"cookiefile": _COOKIES} if _os.path.exists(_COOKIES) else {} ),
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