#!/usr/bin/env python3
"""Tiny CLI to exercise the DigitalCoach API with a local video.

Usage:
    python examples/analyze_video.py path/to/clip.mp4 --exercise "Push-up"
    python examples/analyze_video.py clip.mov -e "Push-up" --url http://localhost:8080

Start the service first:
    uvicorn app.main:app --reload --port 8080
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze a workout video via the DigitalCoach API."
    )
    parser.add_argument("video", help="Path to the local video file.")
    parser.add_argument("--exercise", "-e", required=True, help="Exercise name, e.g. 'Push-up'.")
    parser.add_argument("--url", default="http://localhost:8080", help="Base URL of the service.")
    parser.add_argument("--timeout", type=float, default=180.0, help="Request timeout (seconds).")
    args = parser.parse_args()

    if not os.path.isfile(args.video):
        print(f"File not found: {args.video}", file=sys.stderr)
        return 2

    endpoint = args.url.rstrip("/") + "/api/v1/analyze"
    print(f"POST {endpoint}  (exercise={args.exercise!r}, file={os.path.basename(args.video)})")

    with open(args.video, "rb") as handle:
        response = httpx.post(
            endpoint,
            files={"video": (os.path.basename(args.video), handle, "video/mp4")},
            data={"exercise": args.exercise},
            timeout=args.timeout,
        )

    print(f"HTTP {response.status_code}\n")
    try:
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except ValueError:
        print(response.text)
    return 0 if response.status_code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
