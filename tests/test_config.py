from pathlib import Path

from signalguard.config import load_config


def test_loads_dotenv_config(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    env_path = tmp_path / ".env"
    env_path.write_text(
        """
SIGNALGUARD_NETDATA_URL=http://netdata:19999
SIGNALGUARD_LLM_PROVIDER=openrouter
SIGNALGUARD_LLM_MODEL=openai/gpt-4.1-mini
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
""".strip(),
        encoding="utf-8",
    )

    config = load_config()

    assert config.netdata_url == "http://netdata:19999"
    assert config.llm_provider == "openrouter"
    assert config.llm_model == "openai/gpt-4.1-mini"


def test_env_values_override_dotenv(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    env_path = tmp_path / ".env"
    env_path.write_text(
        """
SIGNALGUARD_LLM_PROVIDER=ollama
SIGNALGUARD_LLM_MODEL=gemma4:latest
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("SIGNALGUARD_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("SIGNALGUARD_LLM_MODEL", "openai/gpt-4.1-mini")

    config = load_config()

    assert config.llm_provider == "openrouter"
    assert config.llm_model == "openai/gpt-4.1-mini"
