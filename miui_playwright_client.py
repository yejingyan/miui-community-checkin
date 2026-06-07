#!/usr/bin/env python3
"""Playwright browser client for Xiaomi Community daily automation.

This module simulates the user's own browser/App WebView environment. It never
solves captcha automatically. Captcha/verify pages are persisted as pending
state for manual handling.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

import miui_state
from miui_api_client import COOKIE_FILE, H5_CHECKIN_LINK

APP_UA = "Mozilla/5.0 (Linux; Android 14; Xiaomi 14) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120 Mobile Safari/537.36 app/vipaccount app/planet"
VERIFY_KEYWORDS = ("captcha", "miverify", "verify.sec.xiaomi.com", "static-verify.sec.xiaomi.com", "geetest")


@dataclass
class H5PageResult:
    status: str  # 已签 / 未签 / 需人工验证 / 登录态失效 / 失败
    verify_url: str = ""
    screenshot: str = ""
    detail: str = ""


class MiuiPlaywrightClient:
    def __init__(self, cookie_file: Path = COOKIE_FILE, headless: bool = True, timeout_ms: int = 90_000) -> None:
        self.cookie_file = cookie_file
        self.headless = headless
        self.timeout_ms = timeout_ms

    def _load_cookie_list(self) -> list[dict[str, Any]]:
        if not self.cookie_file.exists():
            return []
        data = json.loads(self.cookie_file.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [c for c in data if isinstance(c, dict) and c.get("name")]
        if isinstance(data, dict):
            return [{"name": str(k), "value": str(v), "domain": ".miui.com", "path": "/"} for k, v in data.items()]
        return []

    @staticmethod
    def _inject_app_environment(context: BrowserContext) -> None:
        context.add_init_script(
            """
            (() => {
              window.vipAccount = {
                isApp: () => true,
                getApplicationVersion: () => '6.250831.0',
                getAndroidVersion: () => '14',
                getMiuiBigVersion: () => '15',
                getMiuiVersion: () => 'V816.0',
                getMiOSVersion: () => '2.0',
                getDeviceOAID: () => 'unknown-oaid',
                getDevice: () => 'Xiaomi 14',
                getModel: () => 'Xiaomi 14',
                isPad: () => false,
                isFold: () => false,
                getStatusBarHeight: () => 0,
                getNavigationBarHeight: () => 0,
                getNewCutout: () => '',
                getCutout: () => 0,
                isClassicNavigationBarEnabled: () => false,
                isTargetSdk35Enabled: () => false,
                setNavigationBarColor: () => null,
                setNavigationBarColorCompat: () => null,
                setStatusBarDark: () => null,
                enableRefresh: () => null,
                interceptNetWorkReconnect: () => null,
                registerHandler: () => null,
                errorLog: () => null,
                debugToast: () => null,
                getLoginCookie: () => '',
                refreshCookie: () => null,
              };
              window.MiFiHybrid = { isApp: () => true };
            })();
            """
        )

    @staticmethod
    def _body_text(page: Page) -> str:
        try:
            return page.locator("body").inner_text(timeout=10_000)
        except Exception:
            return ""

    @staticmethod
    def _looks_like_verify_challenge_url(url: str) -> bool:
        lowered = (url or "").lower()
        if lowered.endswith("miverify.sdk.js"):
            return False
        return (
            "static-verify.sec.xiaomi.com" in lowered
            or "/v2/html/check.html" in lowered
            or "captcha" in lowered
            or "geetest" in lowered
        )

    @staticmethod
    def _detect_verify_url(page: Page | None, seen_urls: list[str]) -> str:
        if page is not None:
            for frame in page.frames:
                url = frame.url or ""
                if MiuiPlaywrightClient._looks_like_verify_challenge_url(url):
                    return url
        for url in reversed(seen_urls):
            if MiuiPlaywrightClient._looks_like_verify_challenge_url(url):
                return url
        return ""

    @staticmethod
    def _is_signed_text(text: str) -> bool:
        return any(marker in text for marker in ("已签到", "今日已签", "连续签到")) and "立即签到" not in text[:2000]

    @staticmethod
    def _looks_logged_out(text: str, url: str) -> bool:
        lowered_url = url.lower()
        return "account.xiaomi.com" in lowered_url or any(marker in text for marker in ("登录", "账号密码登录", "短信登录")) and "立即签到" not in text


    def browse_recommend_for_growth(self, seconds: int = 15) -> H5PageResult:
        """Open the official recommendation feed long enough to trigger browse growth.

        This only simulates viewing the user's own app feed. It does not post, like,
        comment, or bypass any verification.
        """
        cookies = self._load_cookie_list()
        seen_urls: list[str] = []
        with sync_playwright() as p:
            browser: Browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                viewport={"width": 390, "height": 844},
                is_mobile=True,
                has_touch=True,
                locale="zh-CN",
                user_agent=APP_UA,
            )
            self._inject_app_environment(context)
            if cookies:
                context.add_cookies(cookies)
            page = context.new_page()
            page.on("request", lambda request: seen_urls.append(request.url))
            page.on("response", lambda response: seen_urls.append(response.url))
            try:
                page.goto("https://web-alpha.vip.miui.com/page/info/mio/mio/home?tab=mio&sub_tab=recommend&isInApp=1", wait_until="networkidle", timeout=self.timeout_ms)
                page.wait_for_timeout(5_000)
                text = self._body_text(page)
                if self._looks_logged_out(text, page.url):
                    return H5PageResult(status="登录态失效", detail="recommend feed redirected to login")

                # The growth task says “browse a post for over 10 seconds”, so
                # do not merely idle on the feed. Click a real visible post card
                # and stay on the opened detail page.
                post_candidates = page.locator("div").filter(has_text="05-")
                opened = False
                for i in range(min(post_candidates.count(), 12)):
                    candidate = post_candidates.nth(i)
                    try:
                        box = candidate.bounding_box(timeout=2_000)
                        text_piece = (candidate.inner_text(timeout=2_000) or "").strip()
                    except Exception:
                        continue
                    if not box or box.get("height", 0) < 40 or len(text_piece) < 20:
                        continue
                    before_url = page.url
                    candidate.click(force=True, timeout=5_000)
                    page.wait_for_timeout(3_000)
                    opened = page.url != before_url or "detail" in page.url.lower() or "post" in page.url.lower()
                    if opened:
                        break

                if not opened:
                    return H5PageResult(status="失败", detail="post_candidates found but no post opened")
                page.wait_for_timeout(max(seconds, 11) * 1000)
                text = self._body_text(page)
                if self._looks_logged_out(text, page.url):
                    return H5PageResult(status="登录态失效", detail="post detail redirected to login")
                verify_url = self._detect_verify_url(page, seen_urls)
                if verify_url:
                    screenshot = str(miui_state.screenshot_path("verify_browse_task"))
                    page.screenshot(path=screenshot, full_page=True)
                    miui_state.save_pending(verify_url, source="playwright_browse_task", screenshot=screenshot)
                    return H5PageResult(status="需人工验证", verify_url=verify_url, screenshot=screenshot)
                return H5PageResult(status="已签", detail="post opened and viewed")
            except PlaywrightTimeoutError as exc:
                return H5PageResult(status="失败", detail=f"browse timeout: {exc}")
            except Exception as exc:
                return H5PageResult(status="失败", detail=f"browse error: {exc!r}")
            finally:
                browser.close()

    def inspect_and_click_h5(self) -> H5PageResult:
        cookies = self._load_cookie_list()
        seen_urls: list[str] = []
        with sync_playwright() as p:
            browser: Browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                viewport={"width": 390, "height": 844},
                is_mobile=True,
                has_touch=True,
                locale="zh-CN",
                user_agent=APP_UA,
            )
            self._inject_app_environment(context)
            if cookies:
                context.add_cookies(cookies)
            page = context.new_page()
            page.on("request", lambda request: seen_urls.append(request.url))
            page.on("response", lambda response: seen_urls.append(response.url))
            try:
                page.goto(H5_CHECKIN_LINK, wait_until="networkidle", timeout=self.timeout_ms)
                page.wait_for_timeout(3_000)
                text = self._body_text(page)
                if self._looks_logged_out(text, page.url):
                    return H5PageResult(status="登录态失效", detail="page redirected to login or shows login UI")
                if self._is_signed_text(text):
                    return H5PageResult(status="已签", detail="page text indicates signed")

                button = page.locator("div.checkInBtn-nEos7").first
                if button.count() == 0:
                    button = page.get_by_text("立即签到").first
                if button.count() == 0:
                    verify_url = self._detect_verify_url(page, seen_urls)
                    if verify_url:
                        screenshot = str(miui_state.screenshot_path("verify_found_before_click"))
                        page.screenshot(path=screenshot, full_page=True)
                        miui_state.save_pending(verify_url, source="playwright_h5", screenshot=screenshot)
                        return H5PageResult(status="需人工验证", verify_url=verify_url, screenshot=screenshot)
                    return H5PageResult(status="失败", detail="check-in button not found")

                button.click(force=True, timeout=15_000)
                page.wait_for_timeout(12_000)
                text_after = self._body_text(page)
                verify_url = self._detect_verify_url(page, seen_urls)
                if verify_url:
                    screenshot = str(miui_state.screenshot_path("verify_after_click"))
                    page.screenshot(path=screenshot, full_page=True)
                    miui_state.save_pending(verify_url, source="playwright_h5", screenshot=screenshot)
                    return H5PageResult(status="需人工验证", verify_url=verify_url, screenshot=screenshot)
                if self._is_signed_text(text_after):
                    miui_state.clear_pending()
                    return H5PageResult(status="已签", detail="page text indicates signed after click")
                return H5PageResult(status="未签", detail=text_after[:500])
            except PlaywrightTimeoutError as exc:
                return H5PageResult(status="失败", detail=f"playwright timeout: {exc}")
            except Exception as exc:
                return H5PageResult(status="失败", detail=f"playwright error: {exc!r}")
            finally:
                browser.close()
