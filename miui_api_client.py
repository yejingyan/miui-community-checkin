#!/usr/bin/env python3
"""API client for Xiaomi Community daily automation.

Only uses the user's own logged-in cookies. It does not bypass captcha or forge tokens.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

BASE = Path(__file__).resolve().parent
COOKIE_FILE = BASE / "xiaomi_cookies.json"
ACCOUNT_FILE = BASE / "Daily/data/accounts.json"
H5_CHECKIN_LINK = "https://web-alpha.vip.miui.com/page/info/mio/mio/checkIn"
ALPHA_API_BASE = "https://api-alpha.vip.miui.com"


class LoginExpiredError(RuntimeError):
    pass


class MiuiApiError(RuntimeError):
    pass


@dataclass
class CheckinStatus:
    signed: bool
    today_index: int
    today_value: int | None
    detail: list[Any]
    continuous_days: int | None
    raw: dict[str, Any]


@dataclass
class ExtraTaskResult:
    status: str  # 成功 / 已做过 / 登录态失效 / 失败
    raw: dict[str, Any] | None = None


def load_cookies(cookie_file: Path = COOKIE_FILE) -> dict[str, str]:
    if cookie_file.exists():
        cookies = json.loads(cookie_file.read_text(encoding="utf-8"))
        if isinstance(cookies, list):
            return {str(c.get("name")): str(c.get("value")) for c in cookies if c.get("name")}
        if isinstance(cookies, dict):
            return {str(k): str(v) for k, v in cookies.items()}
    accounts = json.loads(ACCOUNT_FILE.read_text(encoding="utf-8"))
    cookie_str = accounts[0].get("cookie", "")
    parsed: dict[str, str] = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            key, value = part.split("=", 1)
            parsed[key.strip()] = value.strip()
    return parsed


def today_index(now: datetime | None = None) -> int:
    return (now or datetime.now()).weekday()


def alpha_params(cookies: dict[str, str]) -> dict[str, str]:
    return {
        "ref": "",
        "pathname": "/mio/checkIn",
        "version": "dev.20220610",
        "miui_vip_a_ph": cookies.get("miui_vip_a_ph", ""),
    }


def alpha_headers(*, content_type: str | None = None) -> dict[str, str]:
    headers = {
        "Origin": "https://web-alpha.vip.miui.com",
        "Referer": H5_CHECKIN_LINK,
        "User-Agent": "Mozilla/5.0 (Linux; Android 14; Xiaomi 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Mobile Safari/537.36 app/vipaccount app/planet",
        "Accept": "application/json, text/plain, */*",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


class MiuiApiClient:
    def __init__(self, cookies: dict[str, str] | None = None, timeout: float = 30.0) -> None:
        self.cookies = cookies if cookies is not None else load_cookies()
        self.timeout = timeout

    def _request_json(self, method: str, path: str, *, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = ALPHA_API_BASE + "/" + path.lstrip("/")
        response = requests.request(
            method,
            url,
            params=alpha_params(self.cookies),
            headers=alpha_headers(content_type="application/json" if json_body is not None else None),
            cookies=self.cookies,
            json=json_body,
            timeout=self.timeout,
        )
        try:
            data = response.json()
        except Exception as exc:
            raise MiuiApiError(f"non-json response: HTTP {response.status_code}") from exc
        if response.status_code == 401 or data.get("code") == 401:
            raise LoginExpiredError("xiaomi cookie expired")
        return data

    def get_h5_status(self) -> CheckinStatus:
        data = self._request_json("GET", "mtop/planet/vip/user/getUserCheckinInfoV2")
        if data.get("status") != 200:
            raise MiuiApiError(f"unexpected checkin status response: {data}")
        entity = data.get("entity") or {}
        detail = entity.get("checkin7DaysDetail") or []
        idx = today_index()
        value = detail[idx] if len(detail) > idx else None
        signed = bool(value is not None and value > 0)
        days = entity.get("continueCheckInDays")
        return CheckinStatus(
            signed=signed,
            today_index=idx,
            today_value=value,
            detail=detail,
            continuous_days=days if isinstance(days, int) else None,
            raw=data,
        )


    def get_daily_task_items(self) -> list[dict[str, Any]]:
        """Return official daily task cards from the check-in cake page."""
        data = self._request_json("GET", "mtop/planet/vip/member/getCheckinPageCakeList")
        if data.get("status") != 200:
            raise MiuiApiError(f"unexpected task list response: {data}")
        for section in data.get("entity") or []:
            head = section.get("head") or {}
            if head.get("title") == "每日任务":
                return [item for item in section.get("data") or [] if isinstance(item, dict)]
        return []

    def is_browse_post_done_today(self) -> bool:
        for item in self.get_daily_task_items():
            if item.get("title") == "浏览帖子超过10秒":
                return item.get("jumpText") == "已完成"
        # Fallback to grow-up records if the task card shape changes.
        data = self._request_json("GET", "mtop/planet/vip/member/getGrowUpPageData")
        today = datetime.now().strftime("%Y/%m/%d")
        for section in data.get("entity") or []:
            for item in section.get("data") or []:
                if item.get("title") == "浏览帖子" and item.get("desc") == today:
                    return True
        return False

    def has_wechat_extra_record_today(self) -> bool:
        """Return true if today's grow-up records already contain mini-program check-in.

        Xiaomi returns ``status=-1/message=加分失败`` when the mini-program task
        is called after it has already awarded points. Treating that as a hard
        failure made the daily job report a false alarm. The authoritative
        verification is the grow-up record list.
        """
        data = self._request_json("GET", "mtop/planet/vip/member/getGrowUpPageData")
        today = datetime.now().strftime("%Y/%m/%d")
        for section in data.get("entity") or []:
            for item in section.get("data") or []:
                if item.get("title") == "小程序签到" and item.get("desc") == today:
                    return True
        return False

    def run_wechat_extra_task(self) -> ExtraTaskResult:
        """Run official WeChat mini-program grow-up point task.

        This is not H5 main check-in. It is attempted independently each day.
        If the task has already awarded today's +3 points, return 已做过 instead
        of failing the scheduler.
        """
        if self.has_wechat_extra_record_today():
            return ExtraTaskResult(status="已做过", raw={"source": "grow_up_record"})

        url = ALPHA_API_BASE + "/mtop/planet/vip/member/addCommunityGrowUpPointByActionV2"
        alpha_ph = self.cookies.get("miui_vip_a_ph", "")
        alpha_service_token = self.cookies.get("miui_vip_a_serviceToken", "")
        alpha_slh = self.cookies.get("miui_vip_a_slh", "")
        request_cookies = {
            "serviceToken": alpha_service_token,
            "miui_vip_ph": alpha_ph,
            "miui_vip_slh": alpha_slh,
            "miui_vip_a_serviceToken": alpha_service_token,
            "miui_vip_a_ph": alpha_ph,
            "miui_vip_a_slh": alpha_slh,
            "userId": self.cookies.get("userId", ""),
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; MI 8; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/130 Mobile Safari/537.36 MicroMessenger/8.0.56 MiniProgramEnv/android",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded",
            "xweb_xhr": "1",
            "Origin": "https://servicewechat.com",
            "Referer": "https://servicewechat.com/wx240a4a764023c444/7/page-frame.html",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        response = requests.post(
            url,
            headers=headers,
            cookies=request_cookies,
            params={"miui_vip_ph": alpha_ph, "miui_vip_a_ph": alpha_ph},
            data={"action": "WECHAT_CHECKIN_TASK"},
            timeout=self.timeout,
        )
        try:
            data = response.json()
        except Exception as exc:
            raise MiuiApiError(f"extra task non-json response: HTTP {response.status_code}") from exc
        if response.status_code == 401 or data.get("code") == 401:
            return ExtraTaskResult(status="登录态失效", raw=data)
        if data.get("status") == 200:
            return ExtraTaskResult(status="成功", raw=data)
        if self.has_wechat_extra_record_today():
            return ExtraTaskResult(status="已做过", raw=data)
        if data.get("status") == -1 and data.get("message") == "加分失败":
            return ExtraTaskResult(status="失败", raw=data)
        return ExtraTaskResult(status="失败", raw=data)
