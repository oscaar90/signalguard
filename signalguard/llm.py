from __future__ import annotations

import os
from typing import Any

import httpx

from signalguard.config import load_config
from signalguard.models import Diagnosis, Severity


class LLMError(RuntimeError):
    """Raised when the LLM explanation request fails."""


def build_local_explanation(diagnosis: Diagnosis) -> str:
    if not diagnosis.triggered_rules:
        warning_signals = [signal.label for signal in diagnosis.signals if signal.level != Severity.OK]
        if not warning_signals:
            return "No se observan anomalías relevantes en las señales analizadas."
        joined = ", ".join(warning_signals)
        return f"No hay reglas disparadas, pero conviene vigilar estas señales: {joined}."

    rule_names = ", ".join(rule.name for rule in diagnosis.triggered_rules)
    return (
        f"Se detectaron {len(diagnosis.triggered_rules)} regla(s): {rule_names}. "
        f"Hipótesis principal: {diagnosis.hypothesis} "
        f"Siguiente paso sugerido: {diagnosis.next_step}"
    )


def generate_explanation(diagnosis: Diagnosis) -> str:
    config = _resolve_llm_config()
    if config is None:
        return build_local_explanation(diagnosis)

    payload = _build_payload(diagnosis, model=config["model"])
    headers = {"Content-Type": "application/json"}
    if config["provider"] == "openrouter":
        headers["Authorization"] = f"Bearer {config['api_key']}"
        app_name = os.getenv("SIGNALGUARD_APP_NAME")
        app_url = os.getenv("SIGNALGUARD_APP_URL")
        if app_name:
            headers["X-Title"] = app_name
        if app_url:
            headers["HTTP-Referer"] = app_url

    try:
        response = httpx.post(
            f"{config['base_url'].rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
            timeout=config["timeout"],
        )
        response.raise_for_status()
        data = response.json()
        raw_content = data["choices"][0]["message"]["content"]
        if raw_content is None:
            raise LLMError("El proveedor LLM devolvió content=null.")
        content = str(raw_content).strip()
        if not content:
            raise LLMError("El proveedor LLM devolvió una respuesta vacía.")
        return content
    except (httpx.HTTPError, KeyError, IndexError, TypeError, AttributeError) as exc:
        raise LLMError(f"No se pudo generar la explicación LLM: {exc}") from exc


def _resolve_llm_config() -> dict[str, Any] | None:
    app_config = load_config()
    provider = app_config.llm_provider.strip().lower()

    if provider == "none":
        return None

    if provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return None
        return {
            "provider": "openrouter",
            "model": app_config.llm_model,
            "base_url": app_config.openrouter_base_url,
            "api_key": api_key,
            "timeout": 20.0,
        }

    return {
        "provider": "ollama",
        "model": app_config.llm_model,
        "base_url": app_config.ollama_base_url,
        "timeout": 300.0,
    }


def _build_payload(diagnosis: Diagnosis, model: str) -> dict[str, Any]:
    metrics = diagnosis.metrics.to_dict()
    signals = [signal.to_dict() for signal in diagnosis.signals]
    rules = [rule.to_dict() for rule in diagnosis.triggered_rules]

    prompt = (
        "Eres un asistente SRE. Recibirás métricas resumidas y reglas deterministas ya disparadas. "
        "No inventes nuevas métricas ni nuevas causas. No muestres razonamiento interno. "
        "Devuelve solo texto final en español, exactamente en 3 líneas cortas: "
        "Explicación: ... "
        "Hipótesis: ... "
        "Siguiente paso: ..."
    )

    user_content = {
        "status": diagnosis.status.label(),
        "summary": diagnosis.summary,
        "metrics": metrics,
        "signals": signals,
        "triggered_rules": rules,
        "hypothesis": diagnosis.hypothesis,
        "next_step": diagnosis.next_step,
    }

    return {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 400,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": str(user_content)},
        ],
    }
