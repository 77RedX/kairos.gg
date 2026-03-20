import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "kairos_memory.db")
OUT_FILE = os.path.join(BASE_DIR, "database_dump.txt")

def format_duration(seconds):
    if not seconds: return "00:00"
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"

def export_to_txt():
    if not os.path.exists(DB_FILE):
        print("❌ Database file not found!")
        return

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT title, artist_name, release_year, duration_secs, 
                       valence_avg, arousal_avg, valence_std, arousal_std, 
                       default_audio_language, youtube_url 
                FROM track_logs 
                ORDER BY played_at DESC
            """)
            rows = cursor.fetchall()

        with open(OUT_FILE, "w", encoding="utf-8") as f:
            header = (f"{'SONG TITLE':<55} | {'ARTIST':<20} | {'YEAR':<4} | "
                      f"{'DUR':<5} | {'V_AVG':<6} | {'A_AVG':<6} | {'V_STD':<6} | {'A_STD':<6} | "
                      f"{'LANG':<7} | {'URL'}\n")
            f.write(header)
            f.write("-" * 165 + "\n")
            
            for row in rows:
                title, artist, year, dur, v_avg, a_avg, v_std, a_std, lang, url = row
                
                c_title = (title[:52] + '...') if title and len(title) > 55 else (title or "Unknown")
                c_artist = (artist[:17] + '...') if artist and len(artist) > 20 else (artist or "unknown")
                c_year = str(year) if year and year > 0 else "----"
                c_dur = format_duration(dur)
                c_lang = str(lang)[:7] if lang else "unknown"
                
                line = (f"{c_title:<55} | {c_artist:<20} | {c_year:<4} | "
                        f"{c_dur:<5} | {v_avg:>6.2f} | {a_avg:>6.2f} | {v_std:>6.2f} | {a_std:>6.2f} | "
                        f"{c_lang:<7} | {url}\n")
                f.write(line)
                
        print(f"✅ Successfully exported {len(rows)} tracks to {OUT_FILE}")
        
    except Exception as e:
        print(f"❌ Export failed: {e}")

if __name__ == "__main__":
    export_to_txt()