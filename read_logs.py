
import sqlite3

DB_NAME = "liku_memory.db"
AGENT_NAME = "SnapshotAgent"

try:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    print(f"--- Reading last 5 logs for agent: {AGENT_NAME} ---")
    
    # Fetch all types of logs to get a full picture
    c.execute("SELECT timestamp, type, message FROM logs WHERE agent_name=? ORDER BY id DESC LIMIT 5", (AGENT_NAME,))
    rows = c.fetchall()
    
    if not rows:
        print("No logs found for this agent.")
    else:
        for row in reversed(rows): # Print in chronological order
            print(f"[{row[0]}] [{row[1]}] {row[2]}")
            
    conn.close()

except sqlite3.Error as e:
    print(f"Database error: {e}")

except Exception as e:
    print(f"An error occurred: {e}")
