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


MODEL_CHAT = "claude-haiku-4-5-20251001"
MODEL_FEEDBACK = "claude-sonnet-4-6"
MAX_HISTORY_MESSAGES = 12