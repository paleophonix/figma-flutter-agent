"""Hypothesis strategies for synthetic trees (Program 08 P1-a)."""

from __future__ import annotations

from hypothesis import strategies as st

depth_strategy = st.integers(min_value=1, max_value=4)
