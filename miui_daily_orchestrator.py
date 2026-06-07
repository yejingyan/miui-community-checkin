#!/usr/bin/env python3
"""统一执行小米社区每日任务。

稳定入口：
1. miui_daily_playwright.py：统一处理 H5 主签到状态、小程序额外成长值任务、最终状态复查。
2. 如果登录态失效，再尝试 refresh_cookie_auto.py 刷新 cookie 后重跑稳定入口。

退出码策略：
- 0：H5 已签，且小程序额外任务已成功或今天已做过。
- 2/3：需要人工验证或登录态失效。
- 1：真实脚本错误或额外任务确实失败。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent


def python_bin(script: str | None = None) -> str:
    if script in {'refresh_cookie_auto.py', 'interactive_xiaomi_login.py', 'miui_daily_playwright.py'}:
        return sys.executable
    venv_python = BASE / '.venv' / 'bin' / 'python'
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


LAST_OUTPUT = ''


def run_python_step(script: str) -> int:
    global LAST_OUTPUT
    print(f'\n===== [{datetime.now().isoformat(timespec="seconds")}] RUN {script} =====')
    proc = subprocess.run(
        [python_bin(script), script],
        cwd=str(BASE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    LAST_OUTPUT = proc.stdout or ''
    print(LAST_OUTPUT, end='')
    print(f'===== {script} exit={proc.returncode} =====')
    return proc.returncode


def should_refresh_cookie(checkin_code: int, status_code: int, output: str) -> bool:
    if checkin_code == 3:
        return True
    if checkin_code in (0, 2):
        return False
    markers = [
        'HTTP 401',
        'Unauthorized',
        '查询签到状态失败',
        '缺少 miui_vip_a_serviceToken',
        '缺少 miui_vip_a_ph',
        'miui_vip_a_serviceToken / miui_vip_a_ph',
    ]
    return any(marker in output for marker in markers)


def refresh_cookie_if_possible() -> int:
    return run_python_step('refresh_cookie_auto.py')


def notify_human_needed(reason: str, detail: str = '') -> None:
    script = BASE / 'notify_human_needed.py'
    if not script.exists():
        print('MIUI_NOTIFY_MISSING: notify_human_needed.py not found')
        return
    try:
        proc = subprocess.run(
            [sys.executable, str(script), reason, detail],
            cwd=str(BASE),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=35,
        )
        print(proc.stdout, end='')
        print(f'MIUI_NOTIFY_EXIT={proc.returncode}')
    except Exception as exc:
        print(f'MIUI_NOTIFY_ERROR: {exc}')


def scheduler_exit(checkin_code: int, status_code: int) -> int:
    if checkin_code == 0 and status_code == 0:
        return 0
    if checkin_code in (2, 3) or status_code == 2:
        return 2
    if checkin_code not in (0, 2, 3):
        return checkin_code
    return status_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Run MIUI H5 check-in + WeChat extra task + status cleanup')
    parser.add_argument('--skip-status', action='store_true', help='只运行签到尝试，不做最终状态复查')
    args = parser.parse_args(argv)

    checkin_code = run_python_step('miui_daily_playwright.py')
    checkin_output = LAST_OUTPUT
    status_code = 0

    if should_refresh_cookie(checkin_code, status_code, checkin_output):
        print('\nMIUI_COOKIE_EXPIRED_DETECTED: 检测到 cookie 可能失效，尝试模拟浏览器自动刷新。')
        refresh_code = refresh_cookie_if_possible()
        if refresh_code == 0:
            print('MIUI_COOKIE_REFRESH_RETRY: cookie 刷新后重新执行稳定签到流程。')
            checkin_code = run_python_step('miui_daily_playwright.py')
        elif refresh_code == 2:
            print('MIUI_COOKIE_REFRESH_WAITING_HUMAN: 自动登录触发短信/扫码/验证码，需要人工完成。')
            notify_human_needed('短信验证码/账号安全验证', 'cookie 自动刷新时触发')
        else:
            print('MIUI_COOKIE_REFRESH_ERROR: cookie 自动刷新失败。')

    if checkin_code == 2:
        notify_human_needed('小米社区人机验证', 'H5 主签到触发验证码/人机验证')
    elif checkin_code == 3:
        notify_human_needed('登录态失效', '自动刷新未完成，需要人工介入')

    # miui_daily_playwright.py already performs final authoritative H5 verification.
    final = checkin_code
    print(f'\nMIUI_DAILY_ORCHESTRATOR_DONE checkin={checkin_code} status={status_code} final={final}')
    return final


if __name__ == '__main__':
    raise SystemExit(main())
