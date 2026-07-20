PRICING = {
    "groq/llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "gemini/gemini-2.5-flash": {"input": 0.30, "output": 2.50},
}


def calculate_cost(model_used: str, input_tokens: int, output_tokens: int) -> float:
    rates = PRICING[model_used]
    cost = (input_tokens / 1_000_000) * rates["input"] + (output_tokens / 1_000_000) * rates["output"]
    return round(cost, 8)