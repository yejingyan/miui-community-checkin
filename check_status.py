#!/usr/bin/env python3
"""Check Xiaomi Community check-in status and clear pending verify URL if signed."""
from __future__ import annotations

from miui_api_client import LoginExpiredError, MiuiApiClient, MiuiApiError
import verify_pending


def main() -> int:
    try:
        status = MiuiApiClient().get_h5_status()
    except LoginExpiredError:
        print('MIUI_CHECKIN_STATUS_LOGIN_EXPIRED')
        return 3
    except MiuiApiError as exc:
        print(f'MIUI_CHECKIN_STATUS_ERROR: {exc}')
        return 1

    print(
        f'今天索引={status.today_index}，今日值={status.today_value}，'
        f'checkin7DaysDetail={status.detail}'
    )
    if status.signed:
        verify_pending.clear_pending()
        print(
            f'MIUI_CHECKIN_STATUS_SIGNED: 今天已签到，连续签到 {status.continuous_days} 天；pending 已清理。'
        )
        return 0
    pending = verify_pending.load_pending()
    if pending:
        print('MIUI_CHECKIN_STATUS_UNSIGNED_WITH_PENDING')
        print(f"pending_created_at: {pending.get('created_at', '')}")
        print(f"pending_url: {pending.get('url', '')}")
    else:
        print('MIUI_CHECKIN_STATUS_UNSIGNED_NO_PENDING')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
