import json
import time
import requests
from ..config import config


class OllamaClient:
    """HTTP client for local Ollama API."""

    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or config.OLLAMA_URL
        self.model = model or config.OLLAMA_MODEL
        self.timeout = 120

    def is_available(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, model: str = None, retries: int = 3) -> str:
        """Generate a response from Ollama."""
        model = model or self.model
        payload = {"model": model, "prompt": prompt, "stream": False}

        last_error = None
        for attempt in range(retries):
            try:
                resp = requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", "")
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)

        raise RuntimeError(f"Ollama generate failed after {retries} attempts: {last_error}")

    def chat(self, messages: list, model: str = None, retries: int = 3) -> str:
        """Multi-turn conversation with Ollama."""
        model = model or self.model
        payload = {"model": model, "messages": messages, "stream": False}

        last_error = None
        for attempt in range(retries):
            try:
                resp = requests.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("message", {}).get("content", "")
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)

        raise RuntimeError(f"Ollama chat failed after {retries} attempts: {last_error}")

    def generate_json(self, prompt: str, model: str = None) -> dict:
        """Generate a response and parse it as JSON."""
        response = self.generate(prompt, model)
        # Try to extract JSON from response
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to find JSON block in response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
        return {}


ollama_client = OllamaClient()
