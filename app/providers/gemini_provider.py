import time
import os
import asyncio
from google import genai
from google.genai import types
from google.genai.errors import ServerError, ClientError
from app.providers.base import ProviderResponse

GEMINI_MODEL = "gemini-2.5-flash"
MAX_RETRIES = 3


class GeminiProvider:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set in environment")
        self.client = genai.Client(api_key=api_key)

    async def call(self, query: str) -> ProviderResponse:
        start = time.perf_counter()

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.client.aio.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=query,
                    config=types.GenerateContentConfig(max_output_tokens=500),
                )
                break
            except (ServerError, ClientError) as e:
                if attempt == MAX_RETRIES - 1:
                    raise
                wait = 45 if "RESOURCE_EXHAUSTED" in str(e) else 2 ** attempt
                await asyncio.sleep(wait)

        latency_ms = int((time.perf_counter() - start) * 1000)
        usage = response.usage_metadata

        return ProviderResponse(
            text=response.text,
            input_tokens=usage.prompt_token_count,
            output_tokens=usage.candidates_token_count,
            latency_ms=latency_ms,
        )