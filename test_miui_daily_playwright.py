from __future__ import annotations

import miui_daily_playwright as daily
from miui_api_client import CheckinStatus, ExtraTaskResult, LoginExpiredError


class FakeApiNormal:
    def __init__(self) -> None:
        self.extra_called = False
        self.status_calls = 0

    def get_h5_status(self) -> CheckinStatus:
        self.status_calls += 1
        return CheckinStatus(
            signed=True,
            today_index=2,
            today_value=2,
            detail=[2, 5, 2, -1, -1, -1, -1],
            continuous_days=3,
            raw={"status": 200},
        )

    def run_wechat_extra_task(self) -> ExtraTaskResult:
        self.extra_called = True
        return ExtraTaskResult(status="已做过", raw={"status": -1, "message": "加分失败"})


class FakeBrowserNormal:
    def __init__(self) -> None:
        self.called = False

    def inspect_and_click_h5(self):
        self.called = True
        return type("PageResult", (), {"status": "已签"})()


class FakeApiExpired:
    def get_h5_status(self) -> CheckinStatus:
        raise LoginExpiredError("expired")

    def run_wechat_extra_task(self) -> ExtraTaskResult:
        raise AssertionError("extra task should not run when initial login is expired")


class FakeBrowserUnused:
    def inspect_and_click_h5(self):
        raise AssertionError("browser should not run when initial API reports login expired")


def test_signed_h5_still_runs_extra_task() -> None:
    api = FakeApiNormal()
    browser = FakeBrowserNormal()

    result = daily.run_flow(daily.FlowOptions(skip_playwright_when_signed=True, save_result=False), api=api, browser=browser)  # type: ignore[arg-type]

    assert result.h5_status == "已签"
    assert result.extra_status == "已做过"
    assert result.continuous_days == 3
    assert result.need_human is False
    assert result.exit_code == daily.EXIT_OK
    assert api.extra_called is True
    assert browser.called is False


def test_login_expired_returns_distinct_status_and_exit_code() -> None:
    result = daily.run_flow(daily.FlowOptions(save_result=False), api=FakeApiExpired(), browser=FakeBrowserUnused())  # type: ignore[arg-type]

    assert result.h5_status == "登录态失效"
    assert result.extra_status == "登录态失效"
    assert result.need_human is True
    assert result.exit_code == daily.EXIT_LOGIN_EXPIRED
