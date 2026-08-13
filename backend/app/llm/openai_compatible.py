"""OpenAI 호환 Chat Completions 클라이언트.

Gemini(OpenAI 호환 엔드포인트), OpenAI, Groq/Together/OpenRouter/Ollama 등을
같은 코드로 처리한다. httpx 만 사용(무거운 SDK 의존성 없음).
"""
from __future__ import annotations

import httpx

from app.llm.base import LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, base_url: str, api_key: str, model: str, name: str = "openai_compatible"):
        self.base_url = base_url.rstrip("/")
        self.api_key = (api_key or "").strip()
        self.model = model
        self.name = name
        # 실제 API 키는 ASCII(예: AIza...). 한글 placeholder 가 남아있으면 미설정으로 간주.
        key_ok = bool(self.api_key) and self.api_key.isascii()
        self.available = key_ok and bool(model) and bool(self.base_url)

    def chat(self, system: str, user: str, *, temperature: float = 0.7,
             max_tokens: int = 600) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resp = httpx.post(url, json=payload, headers=headers, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        # 일부 모델은 content 가 없거나(예: thinking 토큰 소진) None 일 수 있음 → 안전 추출
        choices = data.get("choices") or []
        if not choices:
            return ""
        content = (choices[0].get("message") or {}).get("content")
        return (content or "").strip()
