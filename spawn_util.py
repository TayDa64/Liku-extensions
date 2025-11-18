import sys, platform, subprocess

def spawn_agent(name: str, goal: str) -> bool:
    cmd = [sys.executable, "agent_runner.py", name, goal]
    system = platform.system()
    try:
        if system == "Windows":
            # Use cmd start to open new window that keeps running
            full = f'start "{name}" cmd /k ' + " ".join(cmd)
            subprocess.Popen(full, shell=True)
        elif system == "Darwin":
            script = f'''tell application "Terminal"\n    do script "python3 {' '.join(cmd)}"\nend tell'''
            subprocess.Popen(["osascript", "-e", script])
        else:
            # Try multiple terminal emulators
            terminals = [
                ("gnome-terminal", ["--"]),
                ("xterm", ["-e"]),
                ("konsole", ["-e"]),
                ("alacritty", ["-e"]),
            ]
            for term, args in terminals:
                try:
                    subprocess.Popen([term] + args + cmd)
                    break
                except FileNotFoundError:
                    continue
        return True
    except Exception:
        return False
