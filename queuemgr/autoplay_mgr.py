import asyncio
import logging
import random
import re
import functools
from autoplay.recommender import get_related, _normalize_title

logger = logging.getLogger(__name__)

# Compile the bad words into a Regex pattern for WHOLE WORD matching (\b)
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

    # Don't fetch if the user already has a queue, or if we are already topped up
    if len(user_q) > 1:
        return

    if len(auto_q) >= 15:
        return

    track = state.current_track.get(guild_id)
    if not track:
        return

    _, title, url = track
    loop = asyncio.get_running_loop()

    try:
        # Wrap the synchronous web request in a try/except block so it doesn't kill the bot on a timeout
        # Using functools.partial is the standard, thread-safe way to pass arguments to run_in_executor
        related = await loop.run_in_executor(None, functools.partial(get_related, url))
    except Exception as e:
        logger.error(f"Autoplay fetch failed for {url}: {e}")
        return

    if not related:
        logger.info("No Related Videos found")
        return
    
    # Force it into a list in case get_related returned a generator, preventing a random.shuffle crash
    related = list(related)
    logger.info(f"Related fetched: {len(related)}")

    history = state.history_set(guild_id)
    curr_norm = _normalize_title(title)

    random.shuffle(related)
    logger.info(f"Autoplay queue size before fill: {len(auto_q)}")

    for candidate_url, candidate_title in related:
        if candidate_url in history:
            continue

        norm = _normalize_title(candidate_title)
        
        if norm == curr_norm:
            continue

        # Use Regex search instead of substring matching
        if BAD_WORDS_PATTERN.search(norm):
            logger.debug(f"Skipped because of bad word: {candidate_title}")
            continue

        auto_q.append((candidate_url, candidate_title))
        logger.info(f"Autoplay added: {candidate_title}")

        if len(auto_q) >= 15:
            break