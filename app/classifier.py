COMPLEX_KEYWORDS = {
    "explain in depth", "compare and contrast", "analyze", "design",
    "architecture", "trade-off", "trade-offs", "pros and cons",
    "step by step", "walk me through", "write code", "debug",
    "optimize", "algorithm", "prove", "derive",
}

SIMPLE_KEYWORDS = {
    "what is", "define", "who is", "when did", "where is",
    "list", "translate", "convert", "spell",
}


def classify(query: str) -> str:
    text = query.lower().strip()

    if any(kw in text for kw in COMPLEX_KEYWORDS):
        return "frontier"

    if any(kw in text for kw in SIMPLE_KEYWORDS):
        return "cheap"

    # Fallback: long queries lean complex, short ones lean cheap
    word_count = len(text.split())
    return "frontier" if word_count > 25 else "cheap"