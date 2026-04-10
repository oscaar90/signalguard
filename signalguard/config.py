from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ENV_PATH = Path(".env")


@dataclass(slots=True)
class AppConfig:
    netdata_url: str = "http://127.0.0.1:19999"
    llm_provider: str = "none"
    llm_model: str = ""
    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    app_name: str = "signalguard"
    app_url: str = "http://localhost"


def load_config() -> AppConfig:
    config = AppConfig()
    _load_dotenv(DEFAULT_ENV_PATH)

    config.netdata_url = os.getenv("SIGNALGUARD_NETDATA_URL", config.netdata_url)
    config.llm_provider = os.getenv("SIGNALGUARD_LLM_PROVIDER", config.llm_provider)
    config.llm_model = os.getenv("SIGNALGUARD_LLM_MODEL", config.llm_model)
    config.ollama_base_url = os.getenv("OLLAMA_BASE_URL", config.ollama_base_url)
    config.openrouter_base_url = os.getenv("OPENROUTER_BASE_URL", config.openrouter_base_url)
    config.app_name = os.getenv("SIGNALGUARD_APP_NAME", config.app_name)
    config.app_url = os.getenv("SIGNALGUARD_APP_URL", config.app_url)
    return config


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
