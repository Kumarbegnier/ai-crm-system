"""Lazy Ollama client singleton to avoid circular imports."""
import ollama

_client: ollama.AsyncClient | None = None


def get_client() -> ollama.AsyncClient:
    global _client
    if _client is None:
        _client = ollama.AsyncClient()
    return _client

