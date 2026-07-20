from typing import Protocol
from dataclasses import dataclass


@dataclass
class ProviderResponse:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


class LLMProvider(Protocol):
    """Every provider (Groq, Gemini, ...) implements this. Router code
    only ever talks to this interface — never to a specific SDK."""

    async def call(self, query: str) -> ProviderResponse: ...