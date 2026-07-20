from pydantic import BaseModel


class ChatRequest(BaseModel):
    query: str


class ChatResponse(BaseModel):
    response: str
    model_used: str
    input_tokens: int
    output_tokens: int
    latency_ms: int