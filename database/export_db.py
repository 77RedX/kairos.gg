import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "kairos_memory.db")
OUT_FILE = os.path.join(BASE_DIR, "database_dump.txt")

def export_to_txt():
    if not os.path.exists(DB_FILE):
        print("❌ Database file not found! Play some songs first.")
        return

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Fetch all the important columns
            cursor.execute("""
                SELECT title, valence_avg, arousal_avg, valence_std, arousal_std, youtube_url 
                FROM track_logs 
                ORDER BY played_at DESC
            """)
            rows = cursor.fetchall()

        with open(OUT_FILE, "w", encoding="utf-8") as f:
            # Write a clean header
            f.write(f"{'SONG TITLE':<55} | {'V_AVG':<6} | {'A_AVG':<6} | {'V_STD':<6} | {'A_STD':<6} | {'URL'}\n")
            f.write("-" * 130 + "\n")
            
            # Write each song
            for row in rows:
                title, v_avg, a_avg, v_std, a_std, url = row
                
                # Truncate super long YouTube titles so they fit neatly in the column
                clean_title = (title[:52] + '...') if len(title) > 55 else title
                
                # Format the numbers to 2 decimal places
                f.write(f"{clean_title:<55} | {v_avg:>6.2f} | {a_avg:>6.2f} | {v_std:>6.2f} | {a_std:>6.2f} | {url}\n")
                
        print(f"✅ Successfully exported {len(rows)} tracks to {OUT_FILE}")
        
    except Exception as e:
        print(f"❌ Export failed: {e}")

if __name__ == "__main__":
    export_to_txt()