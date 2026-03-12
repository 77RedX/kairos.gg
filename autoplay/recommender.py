import yt_dlp
import re
import logging

logger = logging.getLogger(__name__)

YDL_OPTIONS = {
    "quiet": True,
    "skip_download": True,
    "extract_flat": True, # CRITICAL: This stops yt-dlp from downloading metadata for all 50 songs
    "js_runtimes": {
        "node": {}
    }
}

def _normalize_title(title: str):
    if not title:
        return ""
    title = title.lower()
    title = re.sub(r"\(.*?\)", "", title)
    title = re.sub(r"\[.*?\]", "", title)
    title = re.sub(r"official|lyrics|video|audio", "", title)

    return " ".join(title.split())

def extract_video_id(url: str) -> str:
    """Safely extracts the 11-character YouTube video ID from any URL format."""
    # Matches watch?v=ID, youtu.be/ID, shorts/ID, etc.
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})(?:\?|&|/|$)", url)
    if match:
        return match.group(1)
    return None

def get_related(video_url):
    video_id = extract_video_id(video_url)
    if not video_id:
        logger.error(f"Could not extract video ID from url: {video_url}")
        return []

    # RD is YouTube's internal prefix for "Mix" auto-generated playlists
    playlist_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"

    try:
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
            
        entries = info.get("entries", [])
        if not entries:
            return []

        candidates = []
        for e in entries:
            if not e:
                continue

            url = e.get("url") or e.get("webpage_url")
            title = e.get("title")

            if not url or not title:
                continue

            # Ensure we have a full URL (sometimes flat extraction returns just the ID/path)
            if not url.startswith("http"):
                url = f"https://www.youtube.com/watch?v={url}"

            candidates.append((url, title))

        return candidates
        
    except Exception as e:
        logger.error(f"Failed to fetch related videos: {e}")
        return []