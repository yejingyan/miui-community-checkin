from __future__ import annotations

import refresh_cookie_auto as refresh


def test_cookie_required_tokens_are_not_enough_without_successful_login_flow(monkeypatch, tmp_path) -> None:
    cookie_file = tmp_path / "xiaomi_cookies.json"
    cookie_file.write_text(
        '[{"name":"miui_vip_a_serviceToken","value":"old"},{"name":"miui_vip_a_ph","value":"oldph"}]',
        encoding="utf-8",
    )
    monkeypatch.setattr(refresh, "COOKIE_FILE", cookie_file)

    assert refresh.cookie_has_required_tokens() is True
    assert refresh.refresh_succeeded([], process_returncode=1) is False


def test_refresh_success_requires_login_marker_and_tokens(monkeypatch, tmp_path) -> None:
    cookie_file = tmp_path / "xiaomi_cookies.json"
    cookie_file.write_text(
        '[{"name":"miui_vip_a_serviceToken","value":"new"},{"name":"miui_vip_a_ph","value":"newph"}]',
        encoding="utf-8",
    )
    monkeypatch.setattr(refresh, "COOKIE_FILE", cookie_file)

    assert refresh.refresh_succeeded(["LOGIN_PASSED\n"], process_returncode=0) is True
