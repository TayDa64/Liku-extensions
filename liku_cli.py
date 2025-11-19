
import argparse
import sys
import subprocess
import platform
import os
import shlex
import asyncio
from playwright.async_api import async_playwright, Playwright

from spawn_util import spawn_agent
from database import log_event

try:
    import pygetwindow as gw
except ImportError:
    gw = None

def spawn_command(args):
    """Handles the 'spawn' command."""
    print(f"Spawning agent '{args.name}' with goal: '{args.goal}'")
    ok = spawn_agent(args.name, args.goal)
    if ok:
        log_event("LikuCLI", f"Spawn successful for {args.name}", "SPAWN")
        print("Spawn command issued successfully.")
    else:
        log_event("LikuCLI", f"Spawn failed for {args.name}", "ERROR")
        print("Spawn command failed.", file=sys.stderr)

def stream_snapshot_command(args):
    """Handles the 'stream snapshot' command."""
    # Encode to UTF-8 and decode back to the default encoding with error handling
    # to prevent crashes on unprintable characters in window titles.
    safe_input = args.input.encode('utf-8', 'replace').decode(sys.stdout.encoding, 'replace')
    safe_output = args.output.encode('utf-8', 'replace').decode(sys.stdout.encoding, 'replace')
    print(f"Taking a snapshot from '{safe_input}' and saving to '{safe_output}'...")
    
    command = ['ffmpeg', '-y']
    command.extend(shlex.split(args.input))
    command.extend([
        '-vframes', '1',
        args.output
    ])

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"Snapshot saved successfully to {args.output}")
        log_event("LikuCLI", f"Snapshot taken from {args.input}", "STREAM")
    except FileNotFoundError:
        print("Error: 'ffmpeg' not found. Please ensure it is installed and in your system's PATH.", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Error executing ffmpeg: {e}", file=sys.stderr)
        print(f"FFmpeg stderr:\n{e.stderr}", file=sys.stderr)

def stream_record_command(args):
    """Handles the 'stream record' command."""
    print(f"Recording {args.duration} seconds from '{args.input}' to '{args.output}'...")

    command = ['ffmpeg', '-y']
    command.extend(shlex.split(args.input))
    command.extend([
        '-t', str(args.duration),
        args.output
    ])

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"Recording saved successfully to {args.output}")
        log_event("LikuCLI", f"Recorded {args.duration}s from {args.input}", "STREAM")
    except FileNotFoundError:
        print("Error: 'ffmpeg' not found. Please ensure it is installed and in your system's PATH.", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Error executing ffmpeg: {e}", file=sys.stderr)
        print(f"FFmpeg stderr:\n{e.stderr}", file=sys.stderr)

def list_windows_command(args):
    """Handles the 'list-windows' command."""
    if gw is None:
        print("Error: 'pygetwindow' library is not installed. Please install it to use this feature.", file=sys.stderr)
        return

    print("Listing open window titles:")
    windows = gw.getAllWindows()
    for window in windows:
        if window.title:
            print(f"- {window.title}")

async def inspect_web_console(args):
    """Uses Playwright to inspect the web console for errors."""
    print(f"Inspecting console for URL: {args.url}")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        errors = []
        page.on("console", lambda msg: errors.append(msg) if msg.type == "error" else None)
        
        try:
            await page.goto(args.url, wait_until="networkidle")
            print("Page loaded. Found console messages:")
            if errors:
                print("--- CONSOLE ERRORS ---")
                for error in errors:
                    print(f"  - {error.text}")
                print("----------------------")
            else:
                print("  No console errors found.")

        except Exception as e:
            print(f"Error navigating to page: {e}", file=sys.stderr)

        await browser.close()

def inspect_web_command(args):
    """Dispatcher for inspect-web commands."""
    if args.check == "console":
        asyncio.run(inspect_web_console(args))
    else:
        print(f"Error: Unknown check '{args.check}'. Valid options are: console", file=sys.stderr)

def main():
    """Main entry point for the Liku CLI."""
    parser = argparse.ArgumentParser(
        description="Liku CLI: A command-line interface for interacting with Liku agents and tools.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # --- Spawn Command ---
    parser_spawn = subparsers.add_parser("spawn", help="Spawn a new agent.")
    parser_spawn.add_argument("name", help="The name of the agent to spawn.")
    parser_spawn.add_argument("--goal", required=True, help="The goal for the agent to achieve.")
    parser_spawn.set_defaults(func=spawn_command)

    # --- Stream Command ---
    parser_stream = subparsers.add_parser("stream", help="Manage streaming functionalities.")
    stream_subparsers = parser_stream.add_subparsers(dest="stream_command", required=True, help="Stream commands")

    input_help = """
The full ffmpeg input string.
Examples:
  Windows Desktop: -f gdigrab -i desktop
  Windows Webcam:  -f dshow -i video="Your Camera Name"
  Linux Webcam:    -i /dev/video0
"""

    parser_snapshot = stream_subparsers.add_parser("snapshot", help="Take a single snapshot from a video source.")
    parser_snapshot.add_argument("--input", required=True, help=input_help)
    parser_snapshot.add_argument("--output", required=True, help="Path to save the output image file.")
    parser_snapshot.set_defaults(func=stream_snapshot_command)

    parser_record = stream_subparsers.add_parser("record", help="Record a video clip from a source.")
    parser_record.add_argument("--input", required=True, help=input_help)
    parser_record.add_argument("--output", required=True, help="Path to save the output video file.")
    parser_record.add_argument("--duration", type=int, default=15, help="Duration of the recording in seconds (default: 15).")
    parser_record.set_defaults(func=stream_record_command)

    # --- List Windows Command ---
    parser_list_windows = subparsers.add_parser("list-windows", help="List the titles of all open windows.")
    parser_list_windows.set_defaults(func=list_windows_command)

    # --- Inspect Web Command ---
    parser_inspect_web = subparsers.add_parser("inspect-web", help="Inspect a web page using headless browser.")
    parser_inspect_web.add_argument("--url", required=True, help="The URL of the web page to inspect.")
    parser_inspect_web.add_argument("--check", required=True, choices=['console'], help="The specific check to perform.")
    parser_inspect_web.set_defaults(func=inspect_web_command)


    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
