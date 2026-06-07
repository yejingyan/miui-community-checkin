#!/usr/bin/env python3
"""Single entrypoint for Xiaomi Community personal daily automation.

Principles:
- Uses the user's own cookies only.
- Uses Playwright for browser/App-WebView simulation.
- Does not crack captcha, forge tokens, or bypass human verification.
- Captcha/verification means pending state + screenshot + distinct exit code.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

import miui_state
from miui_api_client import ExtraTaskResult, LoginExpiredError, MiuiApiClient, MiuiApiError
from miui_playwright_client import MiuiPlaywrightClient

EXIT_OK = 0
EXIT_NEED_HUMAN = 2
EXIT_LOGIN_EXPIRED = 3
EXIT_ERROR = 1


@dataclass
class FlowOptions:
    skip_playwright_when_signed: bool = False
    headless: bool = True
    save_result: bool = True


def map_extra_status(extra: ExtraTaskResult | None) -> str:
    return extra.status if extra is not None else "未执行"


def run_flow(options: FlowOptions, *, api: MiuiApiClient | None = None, browser: MiuiPlaywrightClient | None = None) -> miui_state.DailyResult:
    api = api or MiuiApiClient()
    browser = browser or MiuiPlaywrightClient(headless=options.headless)

    continuous_days: int | None = None
    h5_status = "失败"
    extra_result: ExtraTaskResult | None = None
    browse_status = "未执行"
    need_human = False
    exit_code = EXIT_ERROR

    try:
        before = api.get_h5_status()
        continuous_days = before.continuous_days
        if before.signed:
            h5_status = "已签"
            miui_state.clear_pending()
            if not options.skip_playwright_when_signed:
                # Still load the page once to exercise the maintained Playwright path.
                page_result = browser.inspect_and_click_h5()
                if page_result.status in ("登录态失效", "需人工验证", "失败"):
                    # API is authoritative for signed state; page trouble should not downgrade a signed day.
                    pass
        else:
            page_result = browser.inspect_and_click_h5()
            h5_status = page_result.status
            if page_result.status == "需人工验证":
                need_human = True
                exit_code = EXIT_NEED_HUMAN
            elif page_result.status == "登录态失效":
                need_human = True
                exit_code = EXIT_LOGIN_EXPIRED
            else:
                try:
                    after = api.get_h5_status()
                    continuous_days = after.continuous_days
                    if after.signed:
                        h5_status = "已签"
                        miui_state.clear_pending()
                    elif h5_status not in ("需人工验证", "登录态失效"):
                        h5_status = "未签"
                except LoginExpiredError:
                    h5_status = "登录态失效"
                    need_human = True
                    exit_code = EXIT_LOGIN_EXPIRED

        # Optional App-side browse task (+1/day). Older tests/fakes may not
        # implement this method, so keep it compatibility-safe.
        has_browse_check = hasattr(api, "is_browse_post_done_today")
        has_browse_runner = hasattr(browser, "browse_recommend_for_growth")
        if has_browse_check and api.is_browse_post_done_today():
            browse_status = "已做过"
        elif has_browse_check and has_browse_runner:
            browse_result = browser.browse_recommend_for_growth()
            browse_status = browse_result.status
            try:
                browse_status = "已做过" if api.is_browse_post_done_today() else browse_status
            except LoginExpiredError:
                browse_status = "登录态失效"
            if browse_status == "需人工验证":
                need_human = True
                exit_code = EXIT_NEED_HUMAN
            elif browse_status == "登录态失效":
                need_human = True
                exit_code = EXIT_LOGIN_EXPIRED

        extra_result = api.run_wechat_extra_task()
        if extra_result.raw is None:
            extra_result.raw = {}
        extra_result.raw["browse_post_status"] = browse_status
        if extra_result.status == "登录态失效":
            if h5_status != "已签":
                h5_status = "登录态失效"
            need_human = True
            exit_code = EXIT_LOGIN_EXPIRED

        # Final authoritative H5 verification.
        try:
            final_status = api.get_h5_status()
            continuous_days = final_status.continuous_days
            if final_status.signed:
                h5_status = "已签"
                miui_state.clear_pending()
            elif h5_status not in ("需人工验证", "登录态失效"):
                h5_status = "未签"
        except LoginExpiredError:
            h5_status = "登录态失效"
            need_human = True
            exit_code = EXIT_LOGIN_EXPIRED

        if h5_status == "需人工验证":
            need_human = True
            exit_code = EXIT_NEED_HUMAN
        elif h5_status == "登录态失效":
            need_human = True
            exit_code = EXIT_LOGIN_EXPIRED
        elif h5_status == "已签" and map_extra_status(extra_result) in ("成功", "已做过"):
            exit_code = EXIT_OK
        elif h5_status == "已签":
            # Main task done; extra failed still needs attention because the mini-program task did not sign.
            if map_extra_status(extra_result) == "失败":
                need_human = True
                exit_code = EXIT_ERROR
            else:
                exit_code = EXIT_OK
        elif h5_status == "未签":
            need_human = True
            exit_code = EXIT_NEED_HUMAN
        else:
            exit_code = EXIT_ERROR

    except LoginExpiredError:
        h5_status = "登录态失效"
        extra_result = extra_result or ExtraTaskResult(status="登录态失效")
        need_human = True
        exit_code = EXIT_LOGIN_EXPIRED
    except MiuiApiError:
        h5_status = "失败"
        extra_result = extra_result or ExtraTaskResult(status="未执行")
        need_human = True
        exit_code = EXIT_ERROR

    extra_status = map_extra_status(extra_result)
    if browse_status not in ("未执行", "已做过"):
        extra_status = f"{extra_status}；浏览帖子：{browse_status}"
    result = miui_state.DailyResult(
        h5_status=h5_status,  # type: ignore[arg-type]
        extra_status=extra_status,  # type: ignore[arg-type]
        continuous_days=continuous_days,
        need_human=need_human,
        exit_code=exit_code,
    )
    if options.save_result:
        miui_state.save_result(result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Xiaomi Community H5 + extra task automation")
    parser.add_argument("--headed", action="store_true", help="Run Playwright with a visible browser")
    parser.add_argument("--skip-playwright-when-signed", action="store_true", help="Only use API if H5 is already signed")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_flow(FlowOptions(skip_playwright_when_signed=args.skip_playwright_when_signed, headless=not args.headed))
    miui_state.print_final_result(result)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
