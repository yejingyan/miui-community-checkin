#!/usr/bin/env python3
"""Send a proactive OpenClaw notification when Xiaomi check-in needs human verification."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
STATE_PATH = BASE / 'notify_human_needed_state.json'
DEFAULT_TARGET = os.environ.get('OPENCLAW_NOTIFY_TARGET', '')
DEFAULT_ACCOUNT = os.environ.get('OPENCLAW_NOTIFY_ACCOUNT', '')
DEFAULT_CHANNEL = os.environ.get('OPENCLAW_NOTIFY_CHANNEL', 'feishu')


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def save_state(state: dict) -> None:
    tmp = STATE_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(STATE_PATH)


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    reason = argv[0] if argv else '需要短信验证码/人机验证'
    detail = ' '.join(argv[1:]).strip()
    today = time.strftime('%Y-%m-%d', time.localtime())
    key = hashlib.sha256(f'{today}|{reason}|{detail}'.encode('utf-8')).hexdigest()[:16]
    state = load_state()
    # Avoid noisy duplicate sends within 10 minutes for the same reason.
    now = int(time.time())
    last = state.get(key, 0)
    if isinstance(last, int) and now - last < 600:
        print(f'MIUI_NOTIFY_SKIP_DUPLICATE key={key}')
        return 0

    target = os.getenv('MIUI_NOTIFY_TARGET') or os.getenv('OPENCLAW_NOTIFY_TARGET') or DEFAULT_TARGET
    account = os.getenv('MIUI_NOTIFY_ACCOUNT') or os.getenv('OPENCLAW_NOTIFY_ACCOUNT') or DEFAULT_ACCOUNT
    channel = os.getenv('MIUI_NOTIFY_CHANNEL') or os.getenv('OPENCLAW_NOTIFY_CHANNEL') or DEFAULT_CHANNEL
    if not target:
        print('MIUI_NOTIFY_TARGET_MISSING: set MIUI_NOTIFY_TARGET or OPENCLAW_NOTIFY_TARGET')
        return 2

    msg = (
        '对象：小米社区签到\n'
        f'目前情况：自动流程卡在{reason}\n'
        f'更新情况：需要老板手动提供验证码或完成人机验证{("；" + detail) if detail else ""}\n'
        '是否需要处理：请把收到的验证码直接发我，我会在同一窗口继续提交。'
    )
    openclaw_bin = os.getenv('OPENCLAW_BIN', '/root/.nvm/versions/node/v22.22.0/bin/openclaw')
    if not Path(openclaw_bin).exists():
        openclaw_bin = 'openclaw'
    cmd = [
        openclaw_bin, 'message', 'send',
        '--channel', channel,
        '--account', account,
        '--target', target,
        '--message', msg,
        '--json',
    ]
    env = os.environ.copy()
    env['PATH'] = '/root/.nvm/versions/node/v22.22.0/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:' + env.get('PATH', '')
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, env=env)
    print(proc.stdout, end='')
    if proc.returncode == 0:
        state[key] = now
        save_state(state)
    return proc.returncode


if __name__ == '__main__':
    raise SystemExit(main())
