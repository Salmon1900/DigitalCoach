#!/usr/bin/env python3
"""PreToolUse guard: block any access to .env / secret files.

Reads the hook payload from stdin. Exit code 2 blocks the tool call and shows the
stderr message back to Claude; exit 0 allows it. Designed to fail open (allow) on any
unexpected error so it never wedges the session.
"""
import json
import os
import sys


def _basename(path: str) -> str:
    return os.path.basename(path.replace("\\", "/").rstrip("/"))


def _is_secret_file(path: str) -> bool:
    if not path:
        return False
    name = _basename(path).lower()
    if name == ".env.example":  # the documented template is safe
        return False
    if name == ".env" or name.startswith(".env."):
        return True
    return name in {"secrets.json", "credentials.json", "service-account.json"}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # fail open

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    # File tools: inspect the target path.
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if _is_secret_file(path):
        print(
            f"Blocked: {tool} on '{path}'. Secret/.env files are off-limits. "
            "Use .env.example for documenting variables.",
            file=sys.stderr,
        )
        return 2

    # Bash: catch obvious attempts to read .env (cat/type/Get-Content .env, etc.).
    if tool == "Bash":
        cmd = (tool_input.get("command") or "").lower()
        if ".env" in cmd and ".env.example" not in cmd:
            print(
                "Blocked: command references .env. Do not read or print secret files.",
                file=sys.stderr,
            )
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
