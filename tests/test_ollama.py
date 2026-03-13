"""Test: Send a test prompt to Ollama, verify JSON response."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_ollama_availability():
    from autoapply.llm.ollama_client import OllamaClient
    client = OllamaClient()
    available = client.is_available()
    print(f"Ollama available: {available}")
    return available


def test_ollama_generate():
    from autoapply.llm.ollama_client import OllamaClient
    client = OllamaClient()

    if not client.is_available():
        print("⚠ Ollama not running — skipping generate test")
        return None

    response = client.generate("Say hello in one sentence.")
    assert response, "Expected non-empty response"
    assert len(response) > 5
    print(f"✓ Ollama generate: '{response[:100]}...'")
    return response


def test_ollama_json_response():
    from autoapply.llm.ollama_client import OllamaClient
    client = OllamaClient()

    if not client.is_available():
        print("⚠ Ollama not running — skipping JSON test")
        return None

    prompt = """Respond ONLY with valid JSON in this format:
{"status": "ok", "message": "hello world", "score": 0.95}
No other text."""

    result = client.generate_json(prompt)
    print(f"✓ Ollama JSON response: {result}")
    return result


def test_job_fit_analysis():
    from autoapply.llm.analyzer import JobAnalyzer
    analyzer = JobAnalyzer()

    from autoapply.llm.ollama_client import OllamaClient
    if not OllamaClient().is_available():
        print("⚠ Ollama not running — skipping fit analysis test")
        return None

    result = analyzer.analyze_fit(
        job_title="Senior Python Developer",
        company="TechCorp",
        job_description="We are looking for a Python expert with 5+ years of experience in FastAPI, PostgreSQL, and AWS.",
        candidate={
            "name": "Jane Doe",
            "skills": "Python, FastAPI, PostgreSQL, Docker, AWS",
            "experience_years": 6,
            "desired_role": "Senior Python Developer",
        },
    )
    print(f"✓ Fit analysis: score={result.get('fit_score')}, recommendation={result.get('recommendation')}")
    assert "fit_score" in result
    assert 0 <= result["fit_score"] <= 1
    return result


if __name__ == "__main__":
    print("Running Ollama tests...")
    test_ollama_availability()
    test_ollama_generate()
    test_ollama_json_response()
    test_job_fit_analysis()
    print("\n✅ Ollama tests complete!")
