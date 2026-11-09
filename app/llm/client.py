"""LLM client that rotates across every configured provider/key."""
from __future__ import annotations
import logging
import httpx

log = logging.getLogger("app.llm.client")

#: OpenAI-compatible chat endpoints: provider -> (base URL, default model).
#: Override models in config/config.toml:  [llm.models]  groq = "..."
PROVIDERS: dict[str, tuple[str, str]] = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash"),
    "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "openrouter": ("https://openrouter.ai/api/v1", "openrouter/auto"),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
}
DEFAULT_ORDER = ("gemini", "groq", "openrouter", "openai")


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, candidates: list[tuple[str, str, str, str]], timeout: float = 120.0):
        """``candidates`` is a list of (provider, base_url, model, api_key), tried in order."""
        self.candidates = candidates
        self._client = httpx.AsyncClient(timeout=timeout)

    @classmethod
    def from_settings(cls, settings) -> "LLMClient":
        cfg = settings.raw.get("llm", {})
        order = cfg.get("order", DEFAULT_ORDER)
        models = cfg.get("models", {})
        candidates = []
        for provider in order:
            if provider not in PROVIDERS:
                continue
            base, model = PROVIDERS[provider]
            for key in settings.keys_for(provider):
                candidates.append((provider, base, models.get(provider, model), key))
        return cls(candidates, timeout=float(cfg.get("timeout", 120)))

    async def generate(self, prompt: str, system: str | None = None, temperature: float = 0.7) -> str:
        if not self.candidates:
            raise LLMError("No LLM API key configured (set GEMINI_API_KEY, GROQ_API_KEY, "
                           "OPEN_ROUTER_API_KEY or OPENAI_API_KEY, or add them to keys.txt).")
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        errors = []
        for provider, base, model, key in self.candidates:
            try:
                resp = await self._client.post(
                    f"{base}/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"model": model, "messages": messages, "temperature": temperature},
                )
                resp.raise_for_status()
                text = resp.json()["choices"][0]["message"]["content"] or ""
                if text.strip():
                    return text
                errors.append(f"{provider}: empty reply")
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                errors.append(f"{provider}: {status or type(e).__name__}")
                log.warning("LLM %s/%s failed (%s), trying next key", provider, model, status or e)
        raise LLMError("All LLM providers failed: " + "; ".join(errors))

    async def aclose(self) -> None:
        await self._client.aclose()
