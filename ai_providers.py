import json
import random
import threading
import os
import ast
from functools import lru_cache

class AllProvidersExhaustedError(Exception):
    """Every configured key, across every provider, failed."""
    pass

class _ProviderClient:
    def __init__(self, provider: str, api_key: str):
        self.provider = provider
        self.api_key = api_key

    def complete(self, prompt: str) -> dict:
        if self.provider == "groq":
            return self._complete_groq(prompt)
        elif self.provider == "gemini":
            return self._complete_gemini(prompt)
        raise ValueError(f"Unknown provider: {self.provider}")

    def _complete_groq(self, prompt: str) -> dict:
        from groq import Groq
        client = Groq(api_key=self.api_key)
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"},
            timeout=20,
        )
        return json.loads(response.choices[0].message.content)

    def _complete_gemini(self, prompt: str) -> dict:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=self.api_key, http_options=types.HttpOptions(timeout=20000))
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                response_mime_type="application/json",
            ),
        )
        return json.loads(response.text)

def _read_key_list(*env_names) -> list:
    """Reads keys from environment variables (like a .env file)."""
    for name in env_names:
        value = os.environ.get(name)
        if not value:
            continue
        try:
            # Try to parse as a JSON list (e.g., '["key1", "key2"]')
            parsed = ast.literal_eval(value)
            if isinstance(parsed, list):
                return parsed
        except (ValueError, SyntaxError):
            pass
        # Fallback: treat as a single comma-separated string or single key
        return [k.strip() for k in value.split(",")]
    return []

@lru_cache(maxsize=None)
def _build_client_pool() -> list:
    groq_keys = _read_key_list("GROQ_API_KEYS", "GROQ_API_KEY")
    gemini_keys = _read_key_list("GEMINI_API_KEYS", "GEMINI_API_KEY")

    pool = (
        [_ProviderClient("groq", k) for k in groq_keys]
        + [_ProviderClient("gemini", k) for k in gemini_keys]
    )
    return pool

_shuffle_lock = threading.Lock()

def get_client_pool() -> list:
    pool = list(_build_client_pool())
    if not pool:
        return pool
    with _shuffle_lock:
        random.shuffle(pool)
    return pool

def has_any_keys_configured() -> bool:
    return len(_build_client_pool()) > 0

def complete_with_rotation(prompt: str, max_attempts: int = None) -> tuple:
    pool = get_client_pool()
    if not pool:
        raise AllProvidersExhaustedError(
            "No AI provider keys configured. Add GROQ_API_KEYS and/or GEMINI_API_KEYS "
            "to your .env file."
        )

    attempts = max_attempts or len(pool)
    last_error = None

    for i in range(attempts):
        client = pool[i % len(pool)]
        try:
            result = client.complete(prompt)
            return result, client.provider
        except Exception as e:
            last_error = f"{client.provider}: {e}"
            continue

    raise AllProvidersExhaustedError(
        f"All {len(pool)} configured AI key(s) failed. Last error: {last_error}"
    )
