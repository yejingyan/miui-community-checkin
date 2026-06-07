from __future__ import annotations

from miui_api_client import ExtraTaskResult
import miui_daily_playwright as daily


class FakeApiExtraFailed:
    def get_h5_status(self):
        return type(
            "CheckinStatusLike",
            (),
            {
                "signed": True,
                "continuous_days": 3,
            },
        )()

    def run_wechat_extra_task(self) -> ExtraTaskResult:
        return ExtraTaskResult(status="失败", raw={"status": -1, "message": "加分失败"})


class FakeBrowserUnused:
    def inspect_and_click_h5(self):
        raise AssertionError("browser should not run when H5 is already signed")


def test_wechat_extra_add_points_failed_needs_human_attention() -> None:
    result = daily.run_flow(
        daily.FlowOptions(skip_playwright_when_signed=True, save_result=False),
        api=FakeApiExtraFailed(),
        browser=FakeBrowserUnused(),  # type: ignore[arg-type]
    )

    assert result.h5_status == "已签"
    assert result.extra_status == "失败"
    assert result.need_human is True
    assert result.exit_code != daily.EXIT_OK
