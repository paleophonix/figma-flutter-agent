"""Tests for preview session port allocation."""

from __future__ import annotations

from control_panel.config.models import PreviewConfig
from control_panel.runner.preview import allocate_preview_ports, build_preview_session


def test_allocate_preview_ports_are_stable_per_job() -> None:
    config = PreviewConfig(static_port_base=17357, adaptive_port_base=17358)
    first = allocate_preview_ports(job_id="job-a", config=config)
    second = allocate_preview_ports(job_id="job-a", config=config)
    assert first == second
    assert first[0] != first[1]


def test_allocate_preview_ports_differ_across_jobs() -> None:
    config = PreviewConfig(static_port_base=17357, adaptive_port_base=17358)
    job_a = allocate_preview_ports(job_id="job-a", config=config)
    job_b = allocate_preview_ports(job_id="job-b", config=config)
    assert job_a != job_b


def test_build_preview_session_uses_allocated_ports() -> None:
    config = PreviewConfig()
    session = build_preview_session(job_id="abc123", config=config)
    expected_static, expected_adaptive = allocate_preview_ports(job_id="abc123", config=config)
    assert session.static_port == expected_static
    assert session.adaptive_port == expected_adaptive
