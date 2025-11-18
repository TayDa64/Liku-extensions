import sqlite3
import time
from datetime import datetime

DB_NAME = "liku_memory.db"

def init_db():
    conn = sqlite3.connect(DB_NAME, timeout=5.0)
    c = conn.cursor()
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute('''CREATE TABLE IF NOT EXISTS agents
                 (name TEXT PRIMARY KEY, status TEXT, current_task TEXT, last_active TIMESTAMP, last_task_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs
                 (id INTEGER PRIMARY KEY, agent_name TEXT, message TEXT,
                  type TEXT, timestamp TIMESTAMP)''')
    # ensure last_task_id column exists if upgrading
    try:
        c.execute("PRAGMA table_info(agents)")
        cols = [r[1] for r in c.fetchall()]
        if "last_task_id" not in cols:
            c.execute("ALTER TABLE agents ADD COLUMN last_task_id INTEGER")
    except Exception:
        pass
    conn.commit()
    conn.close()

def log_event(agent_name: str, message: str, type: str = "INFO") -> None:
    for attempt in range(5):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=5.0)
            c = conn.cursor()
            c.execute("INSERT INTO logs (agent_name, message, type, timestamp) VALUES (?, ?, ?, ?)",
                      (agent_name, message, type, datetime.now()))
            # keep existing last_task_id if present
            existing = c.execute("SELECT last_task_id FROM agents WHERE name=?", (agent_name,)).fetchone()
            last_task_id = existing[0] if existing else None
            c.execute("INSERT OR REPLACE INTO agents (name, status, current_task, last_active, last_task_id) VALUES (?, ?, ?, ?, ?)",
                      (agent_name, "ACTIVE", None, datetime.now(), last_task_id))
            conn.commit()
            conn.close()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < 4:
                time.sleep(0.1 * (attempt + 1))
                continue
            raise

if __name__ == "__main__":
    init_db()
    print("Database initialized at", DB_NAME)
