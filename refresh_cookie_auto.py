#!/usr/bin/env python3
"""Refresh Xiaomi cookies with the existing Playwright login flow.

This script only starts the official Xiaomi login flow in a simulated browser.
If Xiaomi asks for SMS code / QR / captcha, it prints a clear marker and exits
with code 2 so scheduler logs show that human input is required.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
COOKIE_FILE = BASE / 'xiaomi_cookies.json'
LOGIN_SCRIPT = BASE / 'interactive_xiaomi_login.py'


def cookie_has_required_tokens() -> bool:
    if not COOKIE_FILE.exists():
        return False
    try:
        cookies = json.loads(COOKIE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return False
    by_name = {c.get('name'): c.get('value') for c in cookies if isinstance(c, dict)}
    return bool(by_name.get('miui_vip_a_serviceToken') and by_name.get('miui_vip_a_ph'))


def refresh_succeeded(lines: list[str], process_returncode: int | None) -> bool:
    markers = ('LOGIN_PASSED', 'POSSIBLY_PASSED_OR_CHANGED')
    saw_success_marker = any(any(marker in line for marker in markers) for line in lines)
    return bool(process_returncode == 0 and saw_success_marker and cookie_has_required_tokens())


def main() -> int:
    # Playwright is installed in the system Python on this host; the project .venv is for requests-only scripts.
    py = sys.executable
    print('MIUI_COOKIE_REFRESH_START: 启动模拟浏览器官方登录流程')
    proc = subprocess.Popen(
        [py, str(LOGIN_SCRIPT)],
        cwd=str(BASE),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    deadline = time.time() + 90
    lines: list[str] = []
    assert proc.stdout is not None
    while time.time() < deadline:
        line = proc.stdout.readline()
        if line:
            print(line, end='')
            lines.append(line)
            if 'LOGIN_PASSED' in line or 'POSSIBLY_PASSED_OR_CHANGED' in line:
                proc.wait(timeout=10)
                break
            if 'READY_FOR_CODE' in line or 'SEND_CODE_NOW' in line:
                print('MIUI_COOKIE_REFRESH_NEEDS_HUMAN: 小米要求短信/验证码/安全验证，请人工输入；自动流程暂停。')
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()
                return 2
        elif proc.poll() is not None:
            break
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    if refresh_succeeded(lines, proc.returncode):
        print('MIUI_COOKIE_REFRESH_OK: 模拟浏览器登录成功并拿到必要 token')
        return 0
    if cookie_has_required_tokens():
        print('MIUI_COOKIE_REFRESH_FAILED_STALE_COOKIE: 旧 cookie 字段仍存在，但本次模拟登录未成功，不能当作刷新成功')
        return 1
    print('MIUI_COOKIE_REFRESH_FAILED: 未拿到必要 token')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
