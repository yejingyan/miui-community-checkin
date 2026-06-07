#!/usr/bin/env python3
"""State and output helpers for Xiaomi Community daily automation."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

BASE = Path(__file__).resolve().parent
PENDING_FILE = BASE / "miui_verify_pending.json"
RESULT_FILE = BASE / "miui_daily_result.json"
SCREENSHOT_DIR = BASE / "screenshots"

H5Status = Literal["已签", "未签", "需人工验证", "登录态失效", "失败"]
ExtraStatus = Literal["成功", "已做过", "登录态失效", "失败", "未执行"]


@dataclass
class DailyResult:
    h5_status: H5Status
    extra_status: ExtraStatus
    continuous_days: int | None
    need_human: bool
    exit_code: int = 0

    def final_lines(self) -> list[str]:
        return [
            f"H5 主签到结果：{self.h5_status}",
            f"额外任务结果：{self.extra_status}",
            f"连续签到天数：{self.continuous_days if self.continuous_days is not None else '未知'}",
            f"是否需要人工处理：{'是' if self.need_human else '否'}",
        ]


def now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


def screenshot_path(prefix: str = "miui_verify") -> Path:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    safe_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return SCREENSHOT_DIR / f"{prefix}_{safe_ts}.png"


def save_pending(url: str, *, source: str, screenshot: str | None = None, reason: str = "verification_required") -> dict[str, Any]:
    data: dict[str, Any] = {
        "url": url,
        "source": source,
        "reason": reason,
        "screenshot": screenshot or "",
        "created_at": now_text(),
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


def save_result(result: DailyResult) -> None:
    RESULT_FILE.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")


def print_final_result(result: DailyResult) -> None:
    for line in result.final_lines():
        print(line)
