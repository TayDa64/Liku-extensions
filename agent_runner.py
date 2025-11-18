import sys
import time
import random
from database import log_event, init_db


def run_agent(agent_name: str, goal: str) -> None:
    print(f"--- AGENT: {agent_name} ---")
    print(f"Goal: {goal}")
    init_db()
    log_event(agent_name, f"Awakened. Goal: {goal}", "STARTUP")
    if "ffmpeg" in goal.lower():
        scaffold = """#!/usr/bin/env python3
import subprocess, argparse, sys

def build_command(args):
    cmd = ["ffmpeg", "-re", "-i", args.input, "-c:v", args.vcodec, "-b:v", args.bitrate,
           "-c:a", args.acodec, "-f", args.format, args.url]
    return cmd

def run_stream(args):
    cmd = build_command(args)
    print("Executing:", " ".join(cmd))
    p = subprocess.Popen(cmd)
    try:
        p.wait()
    except KeyboardInterrupt:
        p.terminate()
        print("Stream terminated.")

def main():
    parser = argparse.ArgumentParser(description="Simple FFmpeg streaming CLI")
    parser.add_argument("--input", required=True, help="Input media file or device")
    parser.add_argument("--url", required=True, help="Output streaming URL (e.g. rtmp://...) ")
    parser.add_argument("--bitrate", default="2500k", help="Video bitrate")
    parser.add_argument("--vcodec", default="libx264", help="Video codec")
    parser.add_argument("--acodec", default="aac", help="Audio codec")
    parser.add_argument("--format", default="flv", help="Container format (e.g. flv, mpegts)")
    args = parser.parse_args()
    run_stream(args)

if __name__ == "__main__":
    main()
"""
        try:
            with open("streaming_cli.py", "x", encoding="utf-8") as f:
                f.write(scaffold)
            print("[setup] streaming_cli.py scaffold created.")
            log_event(agent_name, "Generated ffmpeg streaming CLI scaffold", "SCAFFOLD")
        except FileExistsError:
            print("[setup] streaming_cli.py already exists; skipping scaffold generation.")
            log_event(agent_name, "FFmpeg scaffold already exists", "SCAFFOLD")

    try:
        while True:
            print(f"[{agent_name}] Thinking...")
            time.sleep(2)
            # check for latest TASK
            import sqlite3
            conn = sqlite3.connect("liku_memory.db")
            c = conn.cursor()
            task_row = c.execute("SELECT id,message FROM logs WHERE type='TASK' ORDER BY id DESC LIMIT 1").fetchone()
            last_task_id = c.execute("SELECT last_task_id FROM agents WHERE name=?", (agent_name,)).fetchone()
            consumed = last_task_id[0] if last_task_id else None
            if task_row and task_row[0] != consumed:
                task_id, task_msg = task_row
                # parse priority like [P2]
                import re
                m = re.match(r"\[P(\d)\]\s*(.*)", task_msg)
                if m:
                    priority = int(m.group(1))
                    task_core = m.group(2)
                else:
                    priority = 1
                    task_core = task_msg
                print(f"[{agent_name}] Consuming TASK {task_id} (P{priority}): {task_core}")
                log_event(agent_name, f"Consumed task {task_id} priority {priority}", "TASK_CONSUMED")
                # simulate result
                result = f"Result for task {task_id}: done"
                log_event(agent_name, result, "RESULT")
                c.execute("UPDATE agents SET last_task_id=? WHERE name=?", (task_id, agent_name))
                conn.commit()
            conn.close()
            action = f"Processed partial task for {goal}"
            print(f"Action: {action}")
            log_event(agent_name, action, "ACTION")
            if random.random() > 0.8:
                user_input = input(f"\n[{agent_name}] Need guidance. What next? > ")
                log_event(agent_name, f"User guidance: {user_input}", "INPUT")
    except KeyboardInterrupt:
        log_event(agent_name, "Agent shutting down", "SHUTDOWN")
        print(f"[{agent_name}] Shutdown.")


def main():
    if len(sys.argv) < 3:
        print("Usage: python agent_runner.py <name> <goal>")
        sys.exit(1)
    run_agent(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
