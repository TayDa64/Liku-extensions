import subprocess
import sys
import platform
import sqlite3
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Input

DB_NAME = "liku_memory.db"

class BookkeeperApp(App):
    CSS = """
    DataTable { height: 1fr; }
    Input { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable()
        yield Input(placeholder="Spawn Agent: <Name> | <Goal>")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Time", "Agent", "Type", "Message")
        self.set_interval(1.0, self.update_dashboard)

    def update_dashboard(self) -> None:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT timestamp, agent_name, type, message FROM logs ORDER BY id DESC LIMIT 20")
        rows = c.fetchall()
        # summary results per agent
        summary = c.execute("SELECT agent_name, COUNT(*) FROM logs WHERE type='RESULT' GROUP BY agent_name").fetchall()
        conn.close()
        table = self.query_one(DataTable)
        table.clear()
        for row in rows:
            table.add_row(*[str(x) for x in row])
        if summary:
            table.add_row("---", "SUMMARY", "RESULTS", ", ".join(f"{a}:{cnt}" for a,cnt in summary))

    def on_input_submitted(self, message: Input.Submitted) -> None:
        try:
            name, goal = message.value.split("|")
            self.spawn_agent_window(name.strip(), goal.strip())
            self.query_one(Input).value = ""
        except ValueError:
            self.notify("Format: Name | Goal", severity="error")

    def spawn_agent_window(self, name: str, goal: str) -> None:
        cmd = [sys.executable, "agent_runner.py", name, goal]
        if platform.system() == "Windows":
            full_cmd = f'start "{name}" cmd /k ' + " ".join(cmd)
            subprocess.Popen(full_cmd, shell=True)
        elif platform.system() == "Darwin":
            script = f'''tell application "Terminal"\n    do script "python3 {' '.join(cmd)}"\nend tell'''
            subprocess.Popen(["osascript", "-e", script])
        else:
            for terminal in (["gnome-terminal", "--"] , ["xterm", "-e"]):
                try:
                    subprocess.Popen(list(terminal) + cmd)
            # convenience: allow entering TASK directly e.g. TASK: Transcode file
        
                    break
                except FileNotFoundError:
                    continue

if __name__ == "__main__":
    from database import init_db
    init_db()
    BookkeeperApp().run()
