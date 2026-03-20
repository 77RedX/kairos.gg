import asyncio
import logging
import random
import re
import functools
from autoplay.recommender import get_related, _normalize_title
from database.database import get_seed_track, get_recommendations

logger = logging.getLogger(__name__)

# ==========================================
# 🎛️ THE MIXING DESK 
# 0.0 = 100% YouTube Discovery
# 0.5 = 50% KaiROS Memory / 50% YouTube
# 1.0 = 100% KaiROS Memory (Needs huge DB)
# ==========================================
KAIROS_WEIGHT = 0.0 
# ==========================================

BAD_WORDS = [
    "remix", "cover", "nightcore", "live", "reaction", 
    "react", "reacts", "review", "analysis", "breakdown",
    "tutorial", "vocal coach", "first time hearing",
    "guitar lesson", "compilation", "compilations"
]
BAD_WORDS_PATTERN = re.compile(r'\b(' + '|'.join(BAD_WORDS) + r')\b', re.IGNORECASE)

async def fill_autoplay(state, guild_id):
    user_q = state.user_q(guild_id)
    auto_q = state.auto_q(guild_id)

    if len(user_q) > 1 or len(auto_q) >= 15:
        return

    track = state.current_track.get(guild_id)
    if not track:
        return

    _, title, url = track
    history = state.history_set(guild_id)
    queued_urls = {q_url for q_url, _ in auto_q}

    logger.info(f"Autoplay queue size before fill: {len(auto_q)}")

    # Lists to hold our raw candidates before we mix them
    db_candidates = []
    yt_candidates = []

    # ---------------------------------------------------------
    # SOURCE 1: KAIROS MEMORY (Only fetch if weight > 0)
    # ---------------------------------------------------------
    if KAIROS_WEIGHT > 0:
        try:
            seed_track = get_seed_track(url, str(guild_id))
            if seed_track:
                _, seed_url, target_v, target_a, seed_lang, seed_artist, seed_year = seed_track
                
                # Fetch more than we strictly need so we have variety
                raw_db_recs = get_recommendations(target_v, target_a, seed_url, seed_lang, seed_artist, seed_year, limit=10)
                
                for rec_title, rec_url, _, _, score in raw_db_recs:
                    if rec_url not in history and rec_url not in queued_urls:
                        db_candidates.append((rec_url, rec_title, score))
                        
        except Exception as e:
            logger.error(f"Failed to fetch DB recommendations for autoplay: {e}")

    # ---------------------------------------------------------
    # SOURCE 2: YOUTUBE DISCOVERY (Only fetch if weight < 1)
    # ---------------------------------------------------------
    if KAIROS_WEIGHT < 1.0:
        loop = asyncio.get_running_loop()
        try:
            related = await loop.run_in_executor(None, functools.partial(get_related, url))
            if related:
                yt_candidates = list(related)
                random.shuffle(yt_candidates) # Shuffle YT to keep things fresh
        except Exception as e:
            logger.error(f"Autoplay YT fetch failed for {url}: {e}")

    # ---------------------------------------------------------
    # THE WEIGHTED MIXER
    # ---------------------------------------------------------
    curr_norm = _normalize_title(title)
    
    while len(auto_q) < 15 and (db_candidates or yt_candidates):
        
        # Decide which source to pull from based on your set weight
        if db_candidates and yt_candidates:
            use_kairos = random.random() < KAIROS_WEIGHT
        elif db_candidates:
            use_kairos = True
        else:
            use_kairos = False

        # Pull from KaiROS Brain
        if use_kairos:
            cand_url, cand_title, score = db_candidates.pop(0)
            
            # DB tracks are already trusted, so we skip the bad word filter
            auto_q.append((cand_url, cand_title))
            queued_urls.add(cand_url)
            history.add(cand_url) # Temporarily add to history so we don't double-pick
            logger.info(f"🧠 DB Match Added: {cand_title} (Score: {score:.3f})")

        # Pull from YouTube
        else:
            cand_url, cand_title = yt_candidates.pop(0)
            
            if cand_url in history or cand_url in queued_urls:
                continue
                
            if not cand_title or not isinstance(cand_title, str):
                continue

            norm = str(_normalize_title(cand_title))
            if norm == curr_norm or BAD_WORDS_PATTERN.search(norm):
                continue

            auto_q.append((cand_url, cand_title))
            queued_urls.add(cand_url)
            history.add(cand_url)
            logger.info(f"🌐 YT Discovery Added: {cand_title}")