import time
import os
from groq import AsyncGroq
from app.providers.base import ProviderResponse

GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = "Be concise: 1-3 sentences, unless code or an in-depth explanation is explicitly requested."


class GroqProvider:
    def __init__(self):
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set in environment")
        self.client = AsyncGroq(api_key=api_key)

    async def call(self, query: str) -> ProviderResponse:
        start = time.perf_counter()

        response = await self.client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            max_tokens=250,
        )

        latency_ms = int((time.perf_counter() - start) * 1000)
        usage = response.usage

        return ProviderResponse(
            text=response.choices[0].message.content,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            latency_ms=latency_ms,
        )