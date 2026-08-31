"""
Wrapper fino em volta do SDK da Anthropic.
Toda a lógica de "conversar com a IA" fica isolada aqui.
"""

import os
import re
import json
import time
from anthropic import Anthropic, APIStatusError, APIConnectionError
from dotenv import load_dotenv

load_dotenv()


def _get_secret(name: str) -> str | None:
    """Lê a chave da API do st.secrets (produção/Streamlit Cloud) com fallback
    para variável de ambiente / .env (desenvolvimento local)."""
    try:
        import streamlit as st
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name)


client = Anthropic(api_key=_get_secret("ANTHROPIC_API_KEY"), timeout=30.0)


def has_api_key() -> bool:
    """Usado pelo app.py pra checar a chave ANTES de tentar conversar,
    e mostrar um aviso claro em vez de um traceback confuso."""
    return bool(_get_secret("ANTHROPIC_API_KEY"))


MODEL_CHAT = "claude-haiku-4-5-20251001"  # falas do cliente — alto volume, precisa ser barato/rápido
MODEL_FEEDBACK = "claude-sonnet-4-6"       # coach final — roda 1x por sessão, prioriza qualidade

MAX_HISTORY_MESSAGES = 12  # ~6 idas e voltas; limita o crescimento de tokens em conversas longas


def _extract_json(text: str, fallback):
    """A IA às vezes cerca o JSON com texto ou markdown — isso limpa e tenta parsear."""
    text = text.strip()
    text = re.sub(r"^```json|```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return fallback


def _call_with_retry(**kwargs):
    """Tenta a chamada até 3x com backoff curto — cobre rate limit/overload
    transitórios, que ficam mais prováveis com vários usuários simultâneos."""
    last_err = None
    for attempt in range(3):
        try:
            return client.messages.create(**kwargs)
        except (APIStatusError, APIConnectionError) as e:
            last_err = e
            status = getattr(e, "status_code", None)
            if status is not None and status != 429 and status < 500:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise last_err


def get_client_reply(system_prompt: str, history: list[dict]) -> dict:
    """
    history: lista de {"role": "user"|"assistant", "content": str}
    Retorna: {"reply": str, "mood": int, "trust": int, "ready_to_buy": bool}
    """
    trimmed_history = history[-MAX_HISTORY_MESSAGES:]
    try:
        response = _call_with_retry(
            model=MODEL_CHAT,
            max_tokens=300,
            cache_control={"type": "ephemeral"},
            system=system_prompt,
            messages=trimmed_history,
        )
    except (APIStatusError, APIConnectionError):
        return {
            "reply": "Desculpa, tive um problema técnico agora. Pode repetir?",
            "mood": 50,
            "trust": 50,
            "ready_to_buy": False,
        }
    text = "".join(block.text for block in response.content if block.type == "text")
    return _extract_json(
        text, {"reply": "Desculpa, pode repetir?", "mood": 50, "trust": 50, "ready_to_buy": False}
    )


def get_feedback(system_prompt: str, transcript: str) -> dict | None:
    """
    Retorna: {"overall_score": int, "summary": str, "strengths": [...],
              "improvements": [...], "best_moment": str, "missed_moment": str}
    """
    try:
        response = _call_with_retry(
            model=MODEL_FEEDBACK,
            max_tokens=800,
            system=system_prompt,
            messages=[{"role": "user", "content": transcript}],
        )
    except (APIStatusError, APIConnectionError):
        return None
    text = "".join(block.text for block in response.content if block.type == "text")
    return _extract_json(text, None)