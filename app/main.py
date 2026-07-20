from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from app.providers.groq_provider import GroqProvider
from app.providers.gemini_provider import GeminiProvider
from app.classifier import classify
from app.schemas import ChatRequest, ChatResponse
from app.services.cache import find_cached_response, save_to_cache
from app.services.pricing import calculate_cost
from app.services.logging_service import log_request


app = FastAPI(title="Tollgate")
groq = GroqProvider()
gemini = GeminiProvider()


@app.post("/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    cached = await find_cached_response(request.query)
    if cached:
        await log_request(
            query_text=request.query,
            model_used=cached["model_used"],
            tier="cached",
            cache_hit=True,
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            latency_ms=0,
        )
        return ChatResponse(
            response=cached["response_text"],
            model_used=cached["model_used"] + " (cached)",
            input_tokens=0,
            output_tokens=0,
            latency_ms=0,
        )

    tier = classify(request.query)
    provider = groq if tier == "cheap" else gemini
    model_name = "groq/llama-3.3-70b-versatile" if tier == "cheap" else "gemini/gemini-2.5-flash"

    result = await provider.call(request.query)
    cost = calculate_cost(model_name, result.input_tokens, result.output_tokens)

    await save_to_cache(request.query, result.text, model_name)
    await log_request(
        query_text=request.query,
        model_used=model_name,
        tier=tier,
        cache_hit=False,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=cost,
        latency_ms=result.latency_ms,
    )

    return ChatResponse(
        response=result.text,
        model_used=model_name,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
    )


@app.get("/health")
async def health():
    return {"status": "ok"}