import sqlite3
from datetime import datetime

DB_NAME = "liku_memory.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS agents
                 (name TEXT PRIMARY KEY, status TEXT, current_task TEXT, last_active TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs
                 (id INTEGER PRIMARY KEY, agent_name TEXT, message TEXT,
                  type TEXT, timestamp TIMESTAMP)''')
    conn.commit()
    conn.close()

def log_event(agent_name: str, message: str, type: str = "INFO") -> None:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO logs (agent_name, message, type, timestamp) VALUES (?, ?, ?, ?)",
              (agent_name, message, type, datetime.now()))
    c.execute("INSERT OR REPLACE INTO agents (name, status, current_task, last_active) VALUES (?, ?, ?, ?)",
              (agent_name, "ACTIVE", None, datetime.now()))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized at", DB_NAME)
