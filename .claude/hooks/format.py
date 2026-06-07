#!/usr/bin/env python3
"""PostToolUse hook: auto-format edited Python files with ruff.

No-ops silently if ruff isn't installed yet, the edit wasn't a .py file, or anything
goes wrong. Always exits 0 so it never interrupts the workflow.
"""
import json
import subprocess
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        path = (payload.get("tool_input", {}) or {}).get("file_path", "")
        if not path or not path.endswith(".py"):
            return 0
        # Format, then apply safe autofixes. Swallow all output/errors.
        for args in (["ruff", "format", path], ["ruff", "check", "--fix", path]):
            subprocess.run(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
