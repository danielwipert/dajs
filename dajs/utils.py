"""Shared utilities."""

from __future__ import annotations

import hashlib


def make_job_id(company: str, title: str, apply_url: str) -> str:
    """Stable SHA-256 identifier for a job. Spec §3.4."""
    payload = "|".join((company.strip().lower(), title.strip().lower(), apply_url.strip()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
