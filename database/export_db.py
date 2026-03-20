import sqlite3
import os

# Set up paths so the script always looks in its own folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "kairos_memory.db")
EXPORT_FILE = os.path.join(BASE_DIR, "kairos_export.txt")

def export_to_txt():
    if not os.path.exists(DB_FILE):
        print(f"❌ Database not found at: {DB_FILE}")
        return

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Fetch everything from the track_logs table
            cursor.execute("SELECT * FROM track_logs")
            rows = cursor.fetchall()
            
            # Dynamically grab the column names (id, guild_id, title, etc.)
            col_names = [description[0] for description in cursor.description]

        # Write to a text file with UTF-8 to prevent emoji/Japanese character crashes
        with open(EXPORT_FILE, "w", encoding="utf-8") as file:
            
            # Write the Header row
            file.write(" | ".join(col_names) + "\n")
            file.write("-" * 150 + "\n")
            
            # Write all the data rows
            for row in rows:
                # Convert numbers/None to strings so they can be joined cleanly
                clean_row = [str(item) if item is not None else "NULL" for item in row]
                file.write(" | ".join(clean_row) + "\n")

        print(f"✅ Successfully exported {len(rows)} tracks to {EXPORT_FILE}")

    except Exception as e:
        print(f"❌ Failed to export database: {e}")

if __name__ == "__main__":
    print("Starting export...")
    export_to_txt()