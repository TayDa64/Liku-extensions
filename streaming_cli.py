#!/usr/bin/env python3
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
