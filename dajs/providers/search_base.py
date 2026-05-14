"""SearchProvider Protocol. Spec §9.2."""

from __future__ import annotations

from typing import Protocol

from dajs.schemas import RawJob


class SearchProvider(Protocol):
    """A source of job postings.

    Implementations: SerpAPIProvider (v1), StubSearchProvider (offline dev).
    """

    def search(self, query: str, params: dict) -> list[RawJob]:
        ...
