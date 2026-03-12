import yt_dlp
import asyncio

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "outtmpl": "downloads/%(id)s.%(ext)s",
    "quiet": True,
    "js_runtimes": {
        "node": {}
    }
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