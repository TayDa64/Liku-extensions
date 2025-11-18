#!/usr/bin/env python3
import platform
import urllib.parse

import subprocess, argparse, sys

def build_command(args):
    in_lower = args.input.lower()
    if in_lower == 'desktop' and platform.system() == 'Windows':
        src = ["-f", "gdigrab", "-framerate", "30", "-i", "desktop"]
    elif in_lower.startswith('dshow:'):
        src = ["-f", "dshow", "-i", args.input.split(':',1)[1]]
    elif in_lower.startswith('avfoundation:'):
        src = ["-f", "avfoundation", "-i", args.input.split(':',1)[1]]
    elif in_lower.startswith('v4l2:'):
        src = ["-f", "v4l2", "-i", args.input.split(':',1)[1]]
    else:
        src = ["-re", "-i", args.input]
    # auto-select container based on URL scheme
    scheme = urllib.parse.urlparse(args.url).scheme.lower()
    out_fmt = args.format
    if scheme in ("rtmp", "rtmps"):
        out_fmt = "flv"
    elif scheme in ("tcp", "udp", "srt"):
        out_fmt = "mpegts"
    cmd = ["ffmpeg"] + src + [
        "-c:v", args.vcodec, "-preset", "veryfast", "-tune", "zerolatency",
        "-b:v", args.bitrate, "-pix_fmt", "yuv420p",
        "-c:a", args.acodec, "-f", out_fmt, args.url
    ]
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
