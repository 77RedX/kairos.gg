import sqlite3
import os
from langdetect import detect, LangDetectException

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "kairos_memory.db")

def guess_unknown_languages():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Find all songs that currently have no language assigned
    cursor.execute("""
        SELECT youtube_url, title 
        FROM track_logs 
        WHERE default_audio_language = 'unknown' OR default_audio_language IS NULL
    """)
    songs = cursor.fetchall()

    print(f"🔍 Found {len(songs)} unknown songs to process.")
    
    if len(songs) == 0:
        print("🎉 No unknown songs found. You are good to go!")
        return

    updates = 0
    for url, title in songs:
        try:
            # Ask the NLP AI to guess the language from the title
            guessed_lang = detect(title)
            
            # YOUR FAILSAFE: If the title is pure ASCII (English letters) 
            # but the AI thinks it's NOT English, force it to 'unknown'
            if title.isascii() and guessed_lang != 'en':
                final_lang = 'unknown'
                print(f"🛡️ Failsafe: '{title[:35]}' (AI guessed {guessed_lang}, forced to unknown)")
            else:
                final_lang = guessed_lang
                print(f"🧠 Guessed '{final_lang:<3}': {title[:35]}")
            
            # Save the result to the database
            if final_lang != 'unknown':
                cursor.execute("""
                    UPDATE track_logs 
                    SET default_audio_language = ? 
                    WHERE youtube_url = ?
                """, (final_lang, url))
                updates += 1
            
        except LangDetectException:
            # This triggers if the title is just emojis or numbers
            print(f"⚠️ Unreadable title: {title[:35]}")
            pass 

    conn.commit()
    conn.close()
    print(f"\n🎉 Sweep complete! Successfully guessed and updated {updates} tracks.")

if __name__ == "__main__":
    guess_unknown_languages()