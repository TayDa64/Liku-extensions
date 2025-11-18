import sqlite3
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Input, Button, Static
from textual.containers import Horizontal, Vertical
from spawn_util import spawn_agent
from database import init_db, log_event

DB_NAME = "liku_memory.db"

class StreamControl(App):
    CSS = """
    Screen { layout: vertical; }
    #top { height: 3; }
    #controls { width: 40%; border: solid green; }
    #streams { width: 60%; }
    DataTable { height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="top"):
            yield Static("Streaming Service Control Center", id="title")
        with Horizontal():
            with Vertical(id="controls"):
                yield Input(placeholder="Name", id="name")
                yield Input(placeholder="Input (file/device)", id="input")
                yield Input(placeholder="URL (rtmp://...)", id="url")
                yield Input(placeholder="Video Bitrate (e.g. 2500k)", id="vbit")
                yield Input(placeholder="Audio Bitrate (e.g. 128k)", id="abit")
                with Horizontal():
                    yield Button("Start", id="start")
                    yield Button("Stop", id="stop")
                    yield Button("Update", id="update")
            with Vertical(id="streams"):
                dt = DataTable(id="table")
                yield dt
        yield Footer()

    def on_mount(self) -> None:
        dt = self.query_one(DataTable)
        dt.add_columns("Name", "Input", "URL", "VBit", "ABit", "Status", "Updated")
        self.set_interval(1.0, self.refresh_streams)

    def refresh_streams(self) -> None:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS streams(
                name TEXT PRIMARY KEY,
                input TEXT,
                url TEXT,
                vbit TEXT,
                abit TEXT,
                status TEXT,
                last_update TIMESTAMP
            )
        """)
        rows = c.execute("SELECT name,input,url,vbit,abit,status,last_update FROM streams ORDER BY name").fetchall()
        conn.close()
        dt = self.query_one(DataTable)
        dt.clear()
        for r in rows:
            dt.add_row(*[str(x) for x in r])

    def action_start(self) -> None:
        self._issue_cmd("START")

    def action_stop(self) -> None:
        self._issue_cmd("STOP")

    def action_update(self) -> None:
        self._issue_cmd("UPDATE")

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id == "start":
            self.action_start()
        elif ev.button.id == "stop":
            self.action_stop()
        elif ev.button.id == "update":
            self.action_update()

    def _issue_cmd(self, cmd: str) -> None:
        name = self.query_one("#name", Input).value.strip() or "stream"
        inp = self.query_one("#input", Input).value.strip()
        url = self.query_one("#url", Input).value.strip()
        vbit = self.query_one("#vbit", Input).value.strip() or "2500k"
        abit = self.query_one("#abit", Input).value.strip() or "128k"
        # upsert stream record
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS streams(
                name TEXT PRIMARY KEY, input TEXT, url TEXT, vbit TEXT, abit TEXT, status TEXT, last_update TIMESTAMP
            )
        """)
        from datetime import datetime
        status = {
            "START": "START_REQUESTED",
            "STOP": "STOP_REQUESTED",
            "UPDATE": "UPDATE_REQUESTED",
        }.get(cmd, "REQUESTED")
        c.execute("INSERT OR REPLACE INTO streams(name,input,url,vbit,abit,status,last_update) VALUES(?,?,?,?,?,?,?)",
                  (name, inp, url, vbit, abit, status, datetime.now()))
        conn.commit()
        conn.close()
        # write TASK for agents to consume
        msg = f"[P2] STREAM_CMD {cmd} {name} input={inp} url={url} vbit={vbit} abit={abit}"
        log_event("ControlCenter", msg, "TASK")
        if cmd == "START":
            # try to spawn dedicated agent
            spawn_agent(f"StreamAgent-{name}", f"ffmpeg streaming for {name}")
            log_event("ControlCenter", f"Spawn requested for StreamAgent-{name}", "SPAWN")

if __name__ == "__main__":
    init_db()
    StreamControl().run()
