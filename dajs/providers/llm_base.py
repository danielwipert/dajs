"""LLMProvider Protocol. Spec §9.2."""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
    """A structured-output LLM completion source.

    Implementations: OpenRouterProvider (v1), StubLLMProvider (offline dev).
    """

    def complete(
        self,
        system: str,
        user: str,
        model: str,
        schema: type[T],
    ) -> T:
        ...
