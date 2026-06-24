"""Tests for HTTP preview proxy token gate."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from control_panel.api.routers.preview import _validate_preview_token, is_public_preview_asset
from control_panel.companion.daemon import hash_token
from control_panel.preview.request import flutter_preview_upstream_path


def test_flutter_preview_upstream_path_maps_base_href() -> None:
    job_id = "abc123"
    assert flutter_preview_upstream_path(job_id=job_id, path="") == "/preview/abc123/"
    assert (
        flutter_preview_upstream_path(job_id=job_id, path="flutter_bootstrap.js")
        == "/preview/abc123/flutter_bootstrap.js"
    )
    assert (
        flutter_preview_upstream_path(job_id=job_id, path="/assets/foo.png")
        == "/preview/abc123/assets/foo.png"
    )


def test_is_public_preview_asset() -> None:
    assert is_public_preview_asset("manifest.json") is True
    assert is_public_preview_asset("/manifest.json") is True
    assert is_public_preview_asset("favicon.png") is True
    assert is_public_preview_asset("flutter_bootstrap.js") is False
    assert is_public_preview_asset("assets/foo.png") is False


def test_validate_preview_token_rejects_missing() -> None:
    with pytest.raises(HTTPException) as exc:
        _validate_preview_token(None, "token")
    assert exc.value.status_code == 401


def test_validate_preview_token_accepts_matching_hash() -> None:
    token = "secret-token"
    _validate_preview_token(hash_token(token), token)
