import os
import shutil

# 1. Base Environment Config
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOCAL_COOKIES = os.path.join(_ROOT_DIR, "cookies.txt")
_HPC_COOKIES = os.path.expanduser("~/kairos.gg/cookies.txt")
_COOKIES = _LOCAL_COOKIES if os.path.exists(_LOCAL_COOKIES) else _HPC_COOKIES

if os.name == 'posix':
    _TMPL = "/dev/shm/kairos_%(id)s.%(ext)s"
    _JS_RUNTIME = {
        "deno": {"path": os.path.expanduser("~/bin/deno-wrapper")},
        "quickjs": {"path": os.path.expanduser("~/bin/qjs")},
    }
else:
    _TMPL = "downloads/%(id)s.%(ext)s"
    _node = shutil.which("node")
    _JS_RUNTIME = {"node": {"path": _node}} if _node else {"node": {}}

# Helper to avoid repeating this logic
def get_base_opts():
    opts = {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "source_address": "0.0.0.0",
        "js_runtimes": _JS_RUNTIME,
    }
    if os.path.exists(_COOKIES):
        opts["cookiefile"] = _COOKIES
    return opts


# 2. Exported Configs for different components

def get_extract_opts():
    """For main.py (Metadata extraction only)"""
    opts = get_base_opts()
    opts.update({
        "format": "bestaudio/best",
        "noplaylist": True,
        "ignoreerrors": True,
    })
    return opts


def filter_duration(info, *, incomplete):
    duration = info.get('duration')
    if duration and duration > 1800:
        return "TOO_LONG"
    return None

def get_download_opts():
    """For playback.py (Actual downloading)"""
    opts = get_base_opts()
    opts.update({
        "format": "bestaudio/best",
        "noplaylist": True,
        "outtmpl": _TMPL,
        "concurrent_fragment_downloads": 10,
        "http_chunk_size": 10485760,
        "match_filter": filter_duration,
    })
    return opts


def get_search_opts():
    """For UI/search_view.py or similar (Search results)"""
    opts = get_base_opts()
    opts.update({
        "extract_flat": True,
        "ignoreerrors": True,
    })
    return opts


def get_related_opts():
    """For autoplay/recommender.py (Fetching related tracks via Mix playlists)"""
    opts = get_base_opts()
    opts.update({
        "skip_download": True,
        "extract_flat": "in_playlist",
        "playlist_items": "1-16",
        "ignoreerrors": True,
    })
    return opts
