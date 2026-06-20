"""Tests for HTTP preview proxy token gate."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from control_panel.api.routers.preview import _validate_preview_token
from control_panel.companion.daemon import hash_token


def test_validate_preview_token_rejects_missing() -> None:
    with pytest.raises(HTTPException) as exc:
        _validate_preview_token(None, "token")
    assert exc.value.status_code == 401


def test_validate_preview_token_accepts_matching_hash() -> None:
    token = "secret-token"
    _validate_preview_token(hash_token(token), token)
