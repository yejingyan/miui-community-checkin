#!/usr/bin/env python3
"""Persist the latest Xiaomi Community verification URL for manual handling."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent
PENDING_FILE = BASE / "miui_verify_pending.json"


def save_pending(url: str, *, source: str = "checkin_v2") -> dict[str, Any]:
    data = {
        "url": url,
        "source": source,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    PENDING_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def load_pending() -> dict[str, Any]:
    if not PENDING_FILE.exists():
        return {}
    try:
        return json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def clear_pending() -> None:
    PENDING_FILE.unlink(missing_ok=True)


def main() -> int:
    data = load_pending()
    if not data:
        print("MIUI_VERIFY_PENDING_EMPTY")
        return 1
    print("MIUI_VERIFY_PENDING")
    print(f"created_at: {data.get('created_at', '')}")
    print(f"source: {data.get('source', '')}")
    print(f"url: {data.get('url', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
