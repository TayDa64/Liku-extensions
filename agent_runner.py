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

    while True:
        print(f"[{agent_name}] Thinking...")
        time.sleep(2)
        action = f"Processed partial task for {goal}"
        print(f"Action: {action}")
        log_event(agent_name, action, "ACTION")
        if random.random() > 0.8:
            user_input = input(f"\n[{agent_name}] Need guidance. What next? > ")
            log_event(agent_name, f"User guidance: {user_input}", "INPUT")


def main():
    if len(sys.argv) < 3:
        print("Usage: python agent_runner.py <name> <goal>")
        sys.exit(1)
    run_agent(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
