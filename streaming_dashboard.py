import sqlite3
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Input, Button, Static, Rule
from textual.containers import Horizontal, Vertical, Container
from spawn_util import spawn_agent
from database import init_db, log_event
import subprocess, platform, re
from datetime import datetime
import logging

DB_NAME = "liku_memory.db"

# Setup logging
logging.basicConfig(filename='streaming_dashboard.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

class StreamControl(App):
    CSS_PATH = "streaming_dashboard.css"

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="app-grid"):
            with Vertical(id="controls"):
                yield Static("Stream Configuration", classes="title")
                yield Static("Name:")
                yield Input(placeholder="e.g., my-stream", id="name")
                yield Static("Input (file/device):")
                yield Input(placeholder="e.g., /dev/video0 or file.mp4", id="input")
                yield Static("URL:")
                yield Input(placeholder="rtmp://a.rtmp.youtube.com/live2", id="url")
                yield Static("Video Bitrate:")
                yield Input(placeholder="e.g., 2500k", id="vbit", value="2500k")
                yield Static("Audio Bitrate:")
                yield Input(placeholder="e.g., 128k", id="abit", value="128k")
                with Horizontal(classes="buttons"):
                    yield Button("Start", id="start", variant="success")
                    yield Button("Stop", id="stop", variant="error")
                    yield Button("Update", id="update")
                with Horizontal(classes="buttons"):
                    yield Button("Stop All", id="stop_all", variant="error")
                    yield Button("Preview", id="preview", variant="primary")

            with Vertical(id="right-panel"):
                with Container(id="streams-container"):
                    yield Static("Active Streams", classes="title")
                    yield DataTable(id="table")
                with Container(id="devices-container"):
                    yield Static("Available Devices", classes="title")
                    yield DataTable(id="devices")
                    with Horizontal(classes="buttons"):
                        yield Button("Scan Devices", id="scan")
                        yield Button("Use Selected", id="use_device")
        yield Footer()

    def on_mount(self) -> None:
        dt = self.query_one('#table', DataTable)
        dt.add_columns("Name", "Input", "URL", "VBit", "ABit", "Status", "Updated")
        dev = self.query_one('#devices', DataTable)
        dev.add_columns("Type", "Name", "Spec")
        self.device_entries = []
        self.set_interval(1.0, self.refresh_streams)
        self.refresh_streams()
        self._scan_devices()

    def refresh_streams(self) -> None:
        try:
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
            dt = self.query_one('#table', DataTable)
            dt.clear()
            for r in rows:
                dt.add_row(*[str(x) for x in r])
        except Exception as e:
            logging.error(f"Failed to refresh streams: {e}")


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
        elif ev.button.id == "scan":
            self._scan_devices()
        elif ev.button.id == "use_device":
            dev = self.query_one('#devices', DataTable)
            if dev.row_count == 0:
                self.notify("No devices to select.", severity="warning")
                return
            try:
                row = dev.get_row_at(dev.cursor_row)
                spec = row[2]
                self.query_one('#input', Input).value = spec
                self.notify(f"Selected device: {row[1]}")
            except Exception as e:
                self.notify(f"Could not select device: {e}", severity="error")
        elif ev.button.id == "stop_all":
            self._stop_all_streams()


    def _issue_cmd(self, cmd: str) -> None:
        name = self.query_one("#name", Input).value.strip() or "stream"
        inp = self.query_one("#input", Input).value.strip()
        url = self.query_one("#url", Input).value.strip()
        vbit = self.query_one("#vbit", Input).value.strip() or "2500k"
        abit = self.query_one("#abit", Input).value.strip() or "128k"
        
        if not inp or not url:
            self.notify("Input and URL fields are required.", severity="error")
            return

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS streams(
                name TEXT PRIMARY KEY, input TEXT, url TEXT, vbit TEXT, abit TEXT, status TEXT, last_update TIMESTAMP
            )
        """)
        status = {
            "START": "START_REQUESTED",
            "STOP": "STOP_REQUESTED",
            "UPDATE": "UPDATE_REQUESTED",
        }.get(cmd, "REQUESTED")
        c.execute("INSERT OR REPLACE INTO streams(name,input,url,vbit,abit,status,last_update) VALUES(?,?,?,?,?,?,?)",
                  (name, inp, url, vbit, abit, status, datetime.now()))
        conn.commit()
        conn.close()
        
        msg = f"[P2] STREAM_CMD {cmd} {name} input={inp} url={url} vbit={vbit} abit={abit}"
        log_event("ControlCenter", msg, "TASK")
        if cmd == "START":
            spawn_agent(f"StreamAgent-{name}", f"ffmpeg streaming for {name}")
            log_event("ControlCenter", f"Spawn requested for StreamAgent-{name}", "SPAWN")

    def _scan_devices(self):
        system = platform.system()
        entries = []
        try:
            if system == 'Windows':
                proc = subprocess.run(['ffmpeg', '-hide_banner', '-f', 'dshow', '-list_devices', 'true', '-i', 'dummy'], capture_output=True, text=True, timeout=10)
                text = proc.stderr
                kind = None
                for line in text.splitlines():
                    if 'DirectShow video devices' in line:
                        kind = 'video'
                    elif 'DirectShow audio devices' in line:
                        kind = 'audio'
                    elif 'Alternative name' not in line and kind:
                        m = re.search(r'\s*"([^"]+)"', line)
                        if m:
                            name = m.group(1)
                            spec = f'dshow:{kind}="{name}"'
                            entries.append((kind, name, spec))
            elif system == 'Darwin':
                proc = subprocess.run(['ffmpeg', '-hide_banner', '-f', 'avfoundation', '-list_devices', 'true', '-i', '""'], capture_output=True, text=True, timeout=10)
                text = proc.stderr
                kind = None
                for line in text.splitlines():
                    if 'AVFoundation video devices' in line:
                        kind = 'video'
                    elif 'AVFoundation audio devices' in line:
                        kind = 'audio'
                    elif kind:
                        m = re.search(r'\[(\d+)\]\s+(.+)$', line.strip())
                        if m:
                            idx, name = m.groups()
                            spec = f'avfoundation:{idx}'
                            entries.append((kind, name, spec))
            else:  # Linux
                try:
                    proc = subprocess.run(['v4l2-ctl', '--list-devices'], capture_output=True, text=True, timeout=10)
                    if proc.returncode == 0:
                        device_name = ""
                        for line in proc.stdout.splitlines():
                            line = line.strip()
                            if not line: continue
                            if not line.startswith('/dev/video'):
                                device_name = line.split(' (')[0]
                            else:
                                spec = line
                                entries.append(('video', device_name, spec))
                except FileNotFoundError:
                    logging.warning("v4l2-ctl not found, skipping video device scan.")
                except Exception as e:
                    logging.error(f"Error scanning v4l2 devices: {e}")

                try:
                    proc = subprocess.run(['arecord', '-l'], capture_output=True, text=True, timeout=10)
                    if proc.returncode == 0:
                        for line in proc.stdout.splitlines():
                            m = re.match(r'card (\d+): .*\[(.*)\].*device (\d+):', line)
                            if m:
                                card, name, device = m.groups()
                                spec = f'alsa:hw:{card},{device}'
                                entries.append(('audio', name.strip(), spec))
                except FileNotFoundError:
                    logging.warning("arecord not found, skipping audio device scan.")
                except Exception as e:
                    logging.error(f"Error scanning ALSA devices: {e}")

        except subprocess.TimeoutExpired:
            self.notify("Device scan timed out.", severity="error")
            logging.error("Device scan timed out.")
        except FileNotFoundError:
            self.notify("ffmpeg not found. Please install and add to PATH.", severity="error")
            logging.error("ffmpeg not found during device scan.")
        except Exception as e:
            self.notify(f"Device scan failed: {e}", severity="error")
            logging.error(f"An error occurred during device scan: {e}")

        self.device_entries = entries
        dev = self.query_one('#devices', DataTable)
        dev.clear()
        if entries:
            for e in entries:
                dev.add_row(*e)
            dev.cursor_type = "row"
            dev.focus()
        else:
            self.notify("No multimedia devices found.")

    def _stop_all_streams(self):
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("CREATE TABLE IF NOT EXISTS streams(name TEXT PRIMARY KEY, input TEXT, url TEXT, vbit TEXT, abit TEXT, status TEXT, last_update TIMESTAMP)")
            rows = c.execute("SELECT name,input,url,vbit,abit FROM streams WHERE COALESCE(status,'') NOT LIKE 'STOP%' ").fetchall()
            
            for name, inp, url, vbit, abit in rows:
                c.execute("UPDATE streams SET status=?, last_update=? WHERE name=?", ("STOP_REQUESTED", datetime.now(), name))
                log_event("ControlCenter", f"[P2] STREAM_CMD STOP {name} input={inp} url={url} vbit={vbit} abit={abit}", "TASK")
            
            conn.commit()
            conn.close()

            if rows:
                self.notify(f"Stop requested for {len(rows)} stream(s).")

            if platform.system() == 'Windows':
                subprocess.run(["powershell", "-NoProfile", "Get-Process ffmpeg -ErrorAction SilentlyContinue | Stop-Process -Force"], check=False)
            else:
                subprocess.run(["pkill", "-f", "ffmpeg"], check=False)
        except Exception as e:
            self.notify(f"Error stopping all streams: {e}", severity="error")
            logging.error(f"Failed to stop all streams: {e}")


if __name__ == "__main__":
    init_db()
    StreamControl().run()
