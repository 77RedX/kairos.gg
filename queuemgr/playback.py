import yt_dlp
import asyncio
import os

if os.name == 'posix':
    _tmpl = "/dev/shm/kairos_%(id)s.%(ext)s"
else:
    _tmpl = "downloads/%(id)s.%(ext)s"

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "outtmpl": _tmpl,
    "quiet": True,
    "js_runtimes": {"node": {}},
    "concurrent_fragment_downloads": 10,
    "http_chunk_size": 10485760,
    "source_address": "0.0.0.0",
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