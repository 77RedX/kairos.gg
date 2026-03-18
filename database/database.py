import sqlite3
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)

# This binds the database path to this specific folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "kairos_memory.db")

def init_db():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS track_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT,
                    title TEXT,
                    youtube_url TEXT UNIQUE,
                    valence_avg REAL,
                    arousal_avg REAL,
                    valence_std REAL,
                    arousal_std REAL,
                    played_at TIMESTAMP
                )
            ''')
            conn.commit()
            logger.info("✅ Database initialized with Average and Std Dev columns.")
    except Exception as e:
        logger.error(f"❌ Database init failed: {e}")

def log_track_emotion(guild_id, title, youtube_url, v_avg, a_avg, v_std, a_std):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO track_logs 
                (guild_id, title, youtube_url, valence_avg, arousal_avg, valence_std, arousal_std, played_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (str(guild_id), title, youtube_url, v_avg, a_avg, v_std, a_std, datetime.now()))
            conn.commit()
    except Exception as e:
        logger.error(f"❌ Failed to log track to DB: {e}")

def check_if_exists(youtube_url):
    """Returns True if the song URL is already in the database."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM track_logs WHERE youtube_url = ?", (youtube_url,))
            # If it finds a row, it returns True. If not, False.
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"❌ Error checking DB for existing track: {e}")
        return False
def get_db_stats():
    """Returns the total number of unique songs and the global average Valence/Arousal."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # COUNT gets the total rows, AVG gets the mathematical mean
            cursor.execute("""
                SELECT COUNT(id), AVG(valence_avg), AVG(arousal_avg) 
                FROM track_logs
            """)
            row = cursor.fetchone()
            
            count = row[0] if row[0] else 0
            avg_v = row[1] if row[1] else 0.0
            avg_a = row[2] if row[2] else 0.0
            
            return count, avg_v, avg_a
    except Exception as e:
        logger.error(f"❌ Failed to get DB stats: {e}")
        return 0, 0.0, 0.0
    
def get_recommendations(target_v, target_a, current_url, limit=5):
    """Finds the closest vibe matches using squared Euclidean distance."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # We use (V2 - V1)^2 + (A2 - A1)^2 directly in the SQL query!
            # It is lightning fast and perfectly accurate for sorting nearest neighbors.
            cursor.execute("""
                SELECT title, youtube_url, valence_avg, arousal_avg,
                       ((valence_avg - ?) * (valence_avg - ?) + (arousal_avg - ?) * (arousal_avg - ?)) as dist
                FROM track_logs
                WHERE youtube_url != ? 
                ORDER BY dist ASC
                LIMIT ?
            """, (target_v, target_v, target_a, target_a, current_url, limit))
            
            return cursor.fetchall()
            
    except Exception as e:
        logger.error(f"❌ Failed to fetch recommendations: {e}")
        return []

def get_track_by_vibe(vibe: str):
    """Pulls a random song from the database based on the 4 emotional quadrants."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Map the vibe to your ML model's coordinates
            if vibe == "hype":      # Happy & Energetic
                condition = "valence_avg > 0 AND arousal_avg > 0"
            elif vibe == "chill":   # Happy & Calm
                condition = "valence_avg > 0 AND arousal_avg <= 0"
            elif vibe == "intense": # Dark & Energetic
                condition = "valence_avg <= 0 AND arousal_avg > 0"
            else:                   # Melancholic & Slow
                condition = "valence_avg <= 0 AND arousal_avg <= 0"
            
            # Fetch 1 random song that matches the condition
            cursor.execute(f"""
                SELECT title, youtube_url, valence_avg, arousal_avg 
                FROM track_logs 
                WHERE {condition}
                ORDER BY RANDOM() LIMIT 1
            """)
            return cursor.fetchone()
            
    except Exception as e:
        logger.error(f"❌ Failed to fetch vibe track: {e}")
        return None

def get_seed_track(current_url: str, guild_id: str):
    """Fetches the current track's coordinates, falling back to the last played track."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # First, try to find the CURRENT song
            cursor.execute("""
                SELECT title, youtube_url, valence_avg, arousal_avg 
                FROM track_logs 
                WHERE youtube_url = ? LIMIT 1
            """, (current_url,))
            seed_track = cursor.fetchone()

            # FALLBACK: If current isn't analyzed, grab the last successfully analyzed song
            if not seed_track:
                logger.info("Current song not analyzed yet. Falling back to last played.")
                cursor.execute("""
                    SELECT title, youtube_url, valence_avg, arousal_avg 
                    FROM track_logs 
                    WHERE guild_id = ? 
                    ORDER BY played_at DESC LIMIT 1
                """, (str(guild_id),))
                seed_track = cursor.fetchone()

            return seed_track
            
    except Exception as e:
        logger.error(f"❌ Failed to fetch seed track: {e}")
        return None