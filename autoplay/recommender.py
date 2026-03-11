import yt_dlp
import random
import re

YDL_OPTIONS = {
    "quiet": True,
    "skip_download": True,
}


def _normalize_title(title: str):
    title = title.lower()

    title = re.sub(r"\(.*?\)", "", title)
    title = re.sub(r"\[.*?\]", "", title)
    title = re.sub(r"official|lyrics|video|remix|live|audio", "", title)

    title = " ".join(title.split())

    return title


def _extract_artist(title: str):
    if " - " in title:
        return title.split(" - ")[0].strip()

    parts = title.split()
    return " ".join(parts[:2])


def get_related(title):

    artist = _extract_artist(title)

    # two stage recommender
    if random.random() < 0.6:
        query = f"ytsearch20:{artist} music"
    else:
        query = f"ytsearch20:{title} music"

    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(query, download=False)

    entries = info.get("entries", [])

    if not entries:
        return None

    bad_words = ["remix", "cover", "nightcore", "live""reaction",
    "reacts",
    "review",
    "analysis",
    "breakdown",
    "tutorial",
    "vocal coach",
    "first time hearing",
    "guitar lesson",
    "compilation",
    "compilations"
]

    candidates = [
        e for e in entries
        if e and not any(w in _normalize_title(e["title"]) for w in bad_words)
    ]

    if not candidates:
        candidates = entries

    choice = random.choice(candidates)

    return choice["webpage_url"], choice["title"]