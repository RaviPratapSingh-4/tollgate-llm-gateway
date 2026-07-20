from sentence_transformers import SentenceTransformer

_model = SentenceTransformer("all-MiniLM-L6-v2")


def embed(text: str) -> list[float]:
    return _model.encode(text).tolist()