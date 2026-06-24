"""Tests for preview proxy HTML helpers."""

from __future__ import annotations

from control_panel.preview.proxy_html import (
    inject_preview_base_href,
    parse_preview_cookie,
    preview_cookie_value,
    rewrite_preview_root_paths,
)


def test_rewrite_preview_root_paths_rewrites_flutter_assets() -> None:
    html = b'<html><script src="/flutter_bootstrap.js"></script></html>'
    updated = rewrite_preview_root_paths(html, job_id="job-1")
    assert b'"/preview/job-1/flutter_bootstrap.js"' in updated


def test_inject_preview_base_href_inserts_under_head() -> None:
    html = b"<html><head><title>x</title></head><body></body></html>"
    updated = inject_preview_base_href(html, job_id="job-1")
    text = updated.decode("utf-8")
    assert '<base href="/preview/job-1/">' in text


def test_preview_cookie_round_trip() -> None:
    raw = preview_cookie_value(job_id="job-1", mode="fixed", token="secret")
    assert parse_preview_cookie(raw) == ("job-1", "fixed", "secret")
