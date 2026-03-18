import yt_dlp
import asyncio
import os

if os.name == 'posix':
    _tmpl = "/dev/shm/kairos_%(id)s.%(ext)s"
else:
    _tmpl = "downloads/%(id)s.%(ext)s"

_js_config = {"node": {}}

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "outtmpl": _tmpl,
    "quiet": True,
    "js_runtimes": _js_config,
    "concurrent_fragment_downloads": 10,
    "http_chunk_size": 10485760,
    "source_address": "0.0.0.0",
    "extractor_args": {
        "youtube": {
            "remote_components": ["ejs:github"],
            "player_client": ["web", "ios"]
        }
    },
}

async def download_track(video_url):

    loop = asyncio.get_running_loop()

    def _dl():

        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)
            title = info.get("title")
            return filename, title

    return await loop.run_in_executor(None, _dl)

# Ultra-fast search options (No downloading, just scraping titles)
SEARCH_OPTIONS = {
    "format": "bestaudio/best",
    "extract_flat": True, 
    "quiet": True,
    "noplaylist": True,
    "no_warnings": True,
    "ignoreerrors": True,
}

async def fetch_search_results(query: str, limit: int = 5):
    """Fetches top N search results from YouTube without downloading."""
    loop = asyncio.get_running_loop()
    
    def _search():
        with yt_dlp.YoutubeDL(SEARCH_OPTIONS) as ydl:
            info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
            if info and "entries" in info:
                return info["entries"][:limit]
            return []
            
    try:
        return await loop.run_in_executor(None, _search)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Search failed for '{query}': {e}")
        return []