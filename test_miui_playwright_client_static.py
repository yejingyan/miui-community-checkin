from __future__ import annotations

from miui_playwright_client import MiuiPlaywrightClient


def test_browse_growth_method_clicks_into_post_detail() -> None:
    source = MiuiPlaywrightClient.browse_recommend_for_growth.__code__.co_consts
    joined = "\n".join(str(x) for x in source)
    assert "post opened" in joined
    assert "post_candidates" in joined


def test_verify_detection_ignores_plain_miverify_sdk_js() -> None:
    assert MiuiPlaywrightClient._detect_verify_url(None, [  # type: ignore[arg-type]
        "https://cdn.vip-community.miui.com/vip--mifans-lts/alpha/v375/static/js/miverify.sdk.js"
    ]) == ""

def test_verify_detection_keeps_real_static_verify_page() -> None:
    assert "static-verify.sec.xiaomi.com" in MiuiPlaywrightClient._detect_verify_url(None, [  # type: ignore[arg-type]
        "https://static-verify.sec.xiaomi.com/v2/html/check.html?t=4"
    ])
