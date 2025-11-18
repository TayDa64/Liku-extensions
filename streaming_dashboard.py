import sqlite3
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Input, Button, Static
from textual.containers import Horizontal, Vertical
from spawn_util import spawn_agent
from database import init_db, log_event
import subprocess, platform, re

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
                    yield Button("Preview", id="preview")
            with Vertical(id="streams"):
                dt = DataTable(id="table")
                yield dt
                with Horizontal():
                    yield Button("Scan Devices", id="scan")
                    yield Button("Use Selected", id="use_device")
                dev = DataTable(id="devices")
                yield dev
        yield Footer()

    def on_mount(self) -> None:
        dt = self.query_one(DataTable)
        dt.add_columns("Name", "Input", "URL", "VBit", "ABit", "Status", "Updated")
        dev = self.query("#devices").first(DataTable)
        dev.add_columns("Type", "Name", "Spec")
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

    def _scan_devices(self):
        system = platform.system()
        entries = []
        try:
            if system == 'Windows':
                # dshow lists devices via stderr
                proc = subprocess.run(['ffmpeg', '-hide_banner', '-f', 'dshow', '-list_devices', 'true', '-i', 'dummy'], capture_output=True, text=True)
                text = proc.stderr
                kind = None
                for line in text.splitlines():
                    if 'DirectShow video devices' in line:
                        kind = 'video'
                    elif 'DirectShow audio devices' in line:
                        kind = 'audio'
                    m = re.search(r'\s*"([^"]+)"', line)
                    if m and kind:
                        name = m.group(1)
                        spec = f'dshow:{kind}="{name}"' if kind == 'video' else f'dshow:{kind}="{name}"'
                        entries.append((kind, name, spec))
            elif system == 'Darwin':
                proc = subprocess.run(['ffmpeg', '-hide_banner', '-f', 'avfoundation', '-list_devices', 'true', '-i', '""'], capture_output=True, text=True)
                text = proc.stderr
                for line in text.splitlines():
                    m = re.search(r'\[(\d+)\] (.+)$', line.strip())
                    if m:
                        idx, name = m.groups()
                        spec = f'avfoundation:{idx}:'
                        entries.append(('avfoundation', name, spec))
            else:
                # Linux: list v4l2 devices via v4l2-ctl if available
                proc = subprocess.run(['bash','-lc','v4l2-ctl --list-devices'], capture_output=True, text=True)
                block = None
                if proc.returncode == 0:
                    for line in proc.stdout.splitlines():
                        if not line.startswith('\t') and line.strip():
                            block = line.strip()
                        elif line.startswith('\t'):
                            dev = line.strip()
                            spec = f'v4l2:{dev}'
                            entries.append(('v4l2', block, spec))
        except Exception:
            pass
        dev = self.query('#devices').first(DataTable)
        dev.clear()
        for e in entries:
            dev.add_row(*e)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id == "start":
            self.action_start()
        elif ev.button.id == "stop":
            self.action_stop()
        elif ev.button.id == "update":
            self.action_update()
        elif ev.button.id == "scan":
            self._scan_devices()
        elif ev.button.id == "use_device":
            dev = self.query('#devices').first(DataTable)
            if dev.row_count:
                row = dev.get_row_at(dev.cursor_row)
                if row and len(row) >= 3:
                    self.query_one('#input', Input).value = row[2]
        elif ev.button.id == "preview":
            spec = self.query_one('#input', Input).value.strip()
            if not spec:
                return
            try:
                system = platform.system()
                if spec.lower() == 'desktop' and system == 'Windows':
                    cmd = ['ffplay','-f','gdigrab','-i','desktop']
                elif spec.startswith('dshow:'):
                    cmd = ['ffplay','-f','dshow','-i', spec.split(':',1)[1]]
                elif spec.startswith('avfoundation:'):
                    cmd = ['ffplay','-f','avfoundation','-i', spec.split(':',1)[1]]
                elif spec.startswith('v4l2:'):
                    cmd = ['ffplay','-f','video4linux2','-i', spec.split(':',1)[1]]
                else:
                    cmd = ['ffplay', spec]
                subprocess.Popen(cmd)
            except Exception:
                pass
            pass
        dev = self.query('#devices').first(DataTable)
        dev.clear()
        for e in entries:
            dev.add_row(*e)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        if ev.button.id == "start":
            self.action_start()
        elif ev.button.id == "stop":
            self.action_stop()
        elif ev.button.id == "update":
            self.action_update()
        elif ev.button.id == "scan":
            self._scan_devices()
        elif ev.button.id == "use_device":
            dev = self.query('#devices').first(DataTable)
            if dev.row_count:
                row = dev.get_row_at(dev.cursor_row)
                if row and len(row) >= 3:
                    self.query_one('#input', Input).value = row[2]
        elif ev.button.id == "preview":
            spec = self.query_one('#input', Input).value.strip()
            if not spec:
                return
            try:
                system = platform.system()
                if spec.lower() == 'desktop' and system == 'Windows':
                    cmd = ['ffplay','-f','gdigrab','-i','desktop']
                elif spec.startswith('dshow:'):
                    cmd = ['ffplay','-f','dshow','-i', spec.split(':',1)[1]]
                elif spec.startswith('avfoundation:'):
                    cmd = ['ffplay','-f','avfoundation','-i', spec.split(':',1)[1]]
                elif spec.startswith('v4l2:'):
                    cmd = ['ffplay','-f','video4linux2','-i', spec.split(':',1)[1]]
                else:
                    cmd = ['ffplay', spec]
                subprocess.Popen(cmd)
            except Exception:
                pass

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
