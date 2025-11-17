#!/usr/bin/env python3
"""
SQLite State Backend with schema migration support and concurrent access management.
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class StateBackend:
    """SQLite-backed state management with migration support."""
    
    # Schema version - increment when making schema changes
    CURRENT_SCHEMA_VERSION = 1
    
    def __init__(self, db_path: str):
        """
        Initialize the state backend.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Connection pool for thread safety
        self._local = threading.local()
        self._lock = threading.RLock()
        
        # Initialize schema
        self._initialize_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA synchronous=NORMAL")
        return self._local.connection
    
    @contextmanager
    def _transaction(self):
        """Context manager for database transactions."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def _initialize_database(self):
        """Initialize database schema and apply migrations."""
        with self._lock, self._transaction() as conn:
            # Create schema version table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Check current version
            cursor = conn.execute("SELECT MAX(version) as ver FROM schema_version")
            row = cursor.fetchone()
            current_version = row['ver'] if row['ver'] is not None else 0
            
            # Apply migrations
            if current_version < self.CURRENT_SCHEMA_VERSION:
                self._apply_migrations(conn, current_version)
    
    def _apply_migrations(self, conn: sqlite3.Connection, from_version: int):
        """
        Apply schema migrations.
        
        Args:
            conn: Database connection
            from_version: Current schema version
        """
        migrations = {
            1: self._migrate_to_v1,
        }
        
        for version in range(from_version + 1, self.CURRENT_SCHEMA_VERSION + 1):
            if version in migrations:
                print(f"Applying migration to version {version}...")
                migrations[version](conn)
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (version,)
                )
    
    def _migrate_to_v1(self, conn: sqlite3.Connection):
        """Initial schema creation."""
        conn.executescript("""
            -- Agent sessions
            CREATE TABLE IF NOT EXISTS agent_session (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                session_key TEXT NOT NULL,
                terminal_id TEXT,
                pid INTEGER,
                status TEXT NOT NULL DEFAULT 'active',
                mode TEXT NOT NULL DEFAULT 'interactive',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(agent_name, session_key)
            );
            
            CREATE INDEX IF NOT EXISTS idx_agent_session_name 
                ON agent_session(agent_name);
            CREATE INDEX IF NOT EXISTS idx_agent_session_status 
                ON agent_session(status);
            
            -- tmux panes
            CREATE TABLE IF NOT EXISTS tmux_pane (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_key TEXT NOT NULL,
                terminal_id TEXT NOT NULL UNIQUE,
                window_name TEXT,
                pane_index INTEGER,
                pane_pid INTEGER,
                status TEXT NOT NULL DEFAULT 'idle',
                last_command TEXT,
                cwd TEXT,
                label TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_tmux_pane_session 
                ON tmux_pane(session_key);
            CREATE INDEX IF NOT EXISTS idx_tmux_pane_terminal 
                ON tmux_pane(terminal_id);
            CREATE INDEX IF NOT EXISTS idx_tmux_pane_status 
                ON tmux_pane(status);
            
            -- Event log
            CREATE TABLE IF NOT EXISTS event_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                session_key TEXT,
                agent_name TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_event_type 
                ON event_log(event_type);
            CREATE INDEX IF NOT EXISTS idx_event_session 
                ON event_log(session_key);
            CREATE INDEX IF NOT EXISTS idx_event_agent 
                ON event_log(agent_name);
            CREATE INDEX IF NOT EXISTS idx_event_created 
                ON event_log(created_at);
            
            -- Guidance records
            CREATE TABLE IF NOT EXISTS guidance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                session_key TEXT NOT NULL,
                instructions TEXT NOT NULL,
                context TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT
            );
            
            CREATE INDEX IF NOT EXISTS idx_guidance_agent 
                ON guidance(agent_name);
            CREATE INDEX IF NOT EXISTS idx_guidance_status 
                ON guidance(status);
            
            -- Approval settings
            CREATE TABLE IF NOT EXISTS approval_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT UNIQUE,
                mode TEXT NOT NULL DEFAULT 'ask',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK(mode IN ('auto', 'ask', 'deny', 'plan-review'))
            );
        """)
    
    # Agent Session Methods
    
    def create_agent_session(
        self,
        agent_name: str,
        session_key: str,
        terminal_id: Optional[str] = None,
        pid: Optional[int] = None,
        mode: str = "interactive"
    ) -> int:
        """Create or update an agent session."""
        with self._lock, self._transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO agent_session 
                (agent_name, session_key, terminal_id, pid, mode, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(agent_name, session_key) 
                DO UPDATE SET 
                    terminal_id=excluded.terminal_id,
                    pid=excluded.pid,
                    mode=excluded.mode,
                    updated_at=CURRENT_TIMESTAMP
                RETURNING id
            """, (agent_name, session_key, terminal_id, pid, mode))
            
            return cursor.fetchone()['id']
    
    def get_agent_session(self, agent_name: str, session_key: str) -> Optional[Dict[str, Any]]:
        """Get agent session by name and session key."""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT * FROM agent_session 
            WHERE agent_name = ? AND session_key = ?
        """, (agent_name, session_key))
        
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_agent_session_by_pane_id(self, pane_id: str) -> Optional[Dict[str, Any]]:
        """Get active agent session by pane ID (terminal_id)."""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT * FROM agent_session 
            WHERE terminal_id = ? AND status = 'active'
        """, (pane_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def list_agent_sessions(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all agent sessions, optionally filtered by status."""
        conn = self._get_connection()
        
        if status:
            cursor = conn.execute(
                "SELECT * FROM agent_session WHERE status = ? ORDER BY updated_at DESC",
                (status,)
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM agent_session ORDER BY updated_at DESC"
            )
        
        return [dict(row) for row in cursor.fetchall()]
    
    def update_agent_status(self, agent_name: str, session_key: str, status: str):
        """Update agent session status."""
        with self._lock, self._transaction() as conn:
            conn.execute("""
                UPDATE agent_session 
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE agent_name = ? AND session_key = ?
            """, (status, agent_name, session_key))
    
    # Tmux Pane Methods
    
    def record_pane(
        self,
        session_key: str,
        terminal_id: str,
        window_name: Optional[str] = None,
        pane_index: Optional[int] = None,
        pane_pid: Optional[int] = None,
        status: str = "idle",
        last_command: Optional[str] = None,
        cwd: Optional[str] = None,
        label: Optional[str] = None
    ) -> int:
        """Record or update a tmux pane."""
        with self._lock, self._transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO tmux_pane 
                (session_key, terminal_id, window_name, pane_index, pane_pid, 
                 status, last_command, cwd, label, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(terminal_id)
                DO UPDATE SET
                    session_key=excluded.session_key,
                    window_name=excluded.window_name,
                    pane_index=excluded.pane_index,
                    pane_pid=excluded.pane_pid,
                    status=excluded.status,
                    last_command=excluded.last_command,
                    cwd=excluded.cwd,
                    label=excluded.label,
                    updated_at=CURRENT_TIMESTAMP
                RETURNING id
            """, (session_key, terminal_id, window_name, pane_index, pane_pid,
                  status, last_command, cwd, label))
            
            return cursor.fetchone()['id']
    
    def get_pane(self, terminal_id: str) -> Optional[Dict[str, Any]]:
        """Get pane by terminal ID."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM tmux_pane WHERE terminal_id = ?",
            (terminal_id,)
        )
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def list_panes(self, session_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all panes, optionally filtered by session."""
        conn = self._get_connection()
        
        if session_key:
            cursor = conn.execute(
                "SELECT * FROM tmux_pane WHERE session_key = ? ORDER BY updated_at DESC",
                (session_key,)
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM tmux_pane ORDER BY updated_at DESC"
            )
        
        return [dict(row) for row in cursor.fetchall()]
    
    # Event Log Methods
    
    def log_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        session_key: Optional[str] = None,
        agent_name: Optional[str] = None
    ) -> int:
        """Log an event to the database."""
        with self._lock, self._transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO event_log 
                (event_type, payload, session_key, agent_name)
                VALUES (?, ?, ?, ?)
            """, (event_type, json.dumps(payload), session_key, agent_name))
            
            return cursor.lastrowid
    
    def get_events(
        self,
        event_type: Optional[str] = None,
        session_key: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get events, optionally filtered."""
        conn = self._get_connection()
        
        query = "SELECT * FROM event_log WHERE 1=1"
        params = []
        
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        
        if session_key:
            query += " AND session_key = ?"
            params.append(session_key)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor = conn.execute(query, params)
        
        events = []
        for row in cursor.fetchall():
            event = dict(row)
            event['payload'] = json.loads(event['payload'])
            events.append(event)
        
        return events
    
    # Guidance Methods
    
    def add_guidance(
        self,
        agent_name: str,
        session_key: str,
        instructions: str,
        context: Optional[str] = None
    ) -> int:
        """Add a guidance record."""
        with self._lock, self._transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO guidance 
                (agent_name, session_key, instructions, context)
                VALUES (?, ?, ?, ?)
            """, (agent_name, session_key, instructions, context))
            
            return cursor.lastrowid
    
    def get_guidance(
        self,
        agent_name: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get guidance records."""
        conn = self._get_connection()
        
        query = "SELECT * FROM guidance WHERE 1=1"
        params = []
        
        if agent_name:
            query += " AND agent_name = ?"
            params.append(agent_name)
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY created_at DESC"
        
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    # Approval Settings Methods
    
    def set_approval_mode(self, agent_name: str, mode: str):
        """Set approval mode for an agent."""
        if mode not in ('auto', 'ask', 'deny', 'plan-review'):
            raise ValueError(f"Invalid approval mode: {mode}")
        
        with self._lock, self._transaction() as conn:
            conn.execute("""
                INSERT INTO approval_settings (agent_name, mode, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(agent_name)
                DO UPDATE SET mode=excluded.mode, updated_at=CURRENT_TIMESTAMP
            """, (agent_name, mode))
    
    def get_approval_mode(self, agent_name: str) -> str:
        """Get approval mode for an agent."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT mode FROM approval_settings WHERE agent_name = ?",
            (agent_name,)
        )
        
        row = cursor.fetchone()
        return row['mode'] if row else 'ask'  # Default to 'ask'
    
    def close(self):
        """Close database connections."""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            del self._local.connection
    
    def close_all_connections(self):
        """Close all database connections (for cleanup in tests)."""
        # Close thread-local connection if exists
        self.close()
        # Note: Threading.local() connections are per-thread, so only close current thread


def main():
    """CLI entry point for testing."""
    import sys
    
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <db_path>")
        sys.exit(1)
    
    db = StateBackend(sys.argv[1])
    
    # Test operations
    print("Testing SQLite State Backend...")
    
    # Create agent session
    session_id = db.create_agent_session(
        "test-agent",
        "session-1",
        terminal_id="liku:0.0",
        pid=12345
    )
    print(f"Created agent session: {session_id}")
    
    # Record pane
    pane_id = db.record_pane(
        "session-1",
        "liku:0.0",
        window_name="general",
        status="running",
        last_command="pytest"
    )
    print(f"Recorded pane: {pane_id}")
    
    # Log event
    event_id = db.log_event(
        "agent.spawn",
        {"agent": "test-agent", "terminal": "liku:0.0"},
        session_key="session-1",
        agent_name="test-agent"
    )
    print(f"Logged event: {event_id}")
    
    # Query data
    sessions = db.list_agent_sessions()
    print(f"\nAgent sessions: {len(sessions)}")
    for session in sessions:
        print(f"  - {session['agent_name']}: {session['status']}")
    
    panes = db.list_panes()
    print(f"\nTmux panes: {len(panes)}")
    for pane in panes:
        print(f"  - {pane['terminal_id']}: {pane['status']}")
    
    events = db.get_events(limit=10)
    print(f"\nRecent events: {len(events)}")
    for event in events:
        print(f"  - {event['event_type']}: {event['payload']}")
    
    db.close()
    print("\nAll tests passed!")


if __name__ == "__main__":
    main()
