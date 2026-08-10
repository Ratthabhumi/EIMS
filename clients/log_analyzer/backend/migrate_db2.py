import sqlite3

def migrate():
    conn = sqlite3.connect("eventiq.db")
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE analysis_history ADD COLUMN username TEXT DEFAULT 'admin'")
        cursor.execute("ALTER TABLE analysis_history ADD COLUMN feedback_by TEXT")
        conn.commit()
        print("Migration successful")
    except Exception as e:
        print("Migration error:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
