import json
import re
import time

import requests

from ..config import config


class OpenRouterClient:
    """HTTP client for OpenRouter AI API (OpenAI-compatible)."""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or config.OPENROUTER_API_KEY
        self.model = model or config.OPENROUTER_MODEL
        self.base_url = config.OPENROUTER_BASE_URL
        self.timeout = 120

    def is_available(self) -> bool:
        """Check if OpenRouter API is reachable and API key is configured."""
        if not self.api_key:
            return False
        try:
            resp = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, model: str = None, retries: int = 3) -> str:
        """Generate a response using a single user prompt."""
        return self.chat(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            retries=retries,
        )

    def chat(self, messages: list, model: str = None, retries: int = 3) -> str:
        """Multi-turn conversation with OpenRouter."""
        model = model or self.model
        payload = {"model": model, "messages": messages}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://autoapply.app",
            "X-Title": "AutoApply",
        }

        last_error = None
        for attempt in range(retries):
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)

        raise RuntimeError(
            f"OpenRouter request failed after {retries} attempts: {last_error}"
        )

    def generate_json(self, prompt: str, model: str = None) -> dict:
        """Generate a response and parse it as JSON."""
        response = self.generate(prompt, model)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
        return {}


openrouter_client = OpenRouterClient()
