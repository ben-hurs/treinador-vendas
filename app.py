"""
Treino de Vendas — app principal (Streamlit).
Rodar com: streamlit run app.py
"""

import streamlit as st
import db
from personas import SCENARIOS
import claude_client
from claude_client import get_client_reply, get_feedback

if not claude_client.has_api_key():
    st.error(
        "⚠️ A chave ANTHROPIC_API_KEY não foi encontrada. "
        "Se você é o administrador do app: confira Settings → Secrets "
        "no Streamlit Cloud e reinicie o app (Reboot app)."
    )
    st.stop()

st.set_page_config(page_title="Treino de Vendas", page_icon="🤝", layout="centered")

# --- setup do banco (roda uma vez, é idempotente) ---
db.init_db()
db.seed_scenarios(SCENARIOS)

# --- estado da sessão do Streamlit ---
if "screen" not in st.session_state:
    st.session_state.screen = "setup"
    st.session_state.scenario = None
    st.session_state.session_id = None
    st.session_state.mood = 50
    st.session_state.trust = 50
    st.session_state.api_history = []
    st.session_state.feedback = None


def start_session(scenario: dict):
    st.session_state.scenario = scenario
    st.session_state.session_id = db.create_session(scenario["id"])
    st.session_state.mood = 50
    st.session_state.trust = 50
    st.session_state.api_history = []
    st.session_state.feedback = None
    st.session_state.screen = "chat"


def build_client_system_prompt(scenario: dict) -> str:
    return f"""{scenario['system_prompt']}

Regras estritas:
- Nunca saia do personagem e nunca mencione que é uma IA ou uma simulação.
- Reaja de forma realista às falas do vendedor: se ele for convincente e tratar bem
  suas objeções, fique mais receptivo (mood e trust sobem); se for insistente ou
  ignorar objeções, fique mais resistente (mood e trust caem).
- Responda sempre em português do Brasil, em 1 a 4 frases, como fala uma pessoa real.
- Responda APENAS com um objeto JSON válido, sem markdown, no formato exato:
{{"reply": "sua fala como cliente", "mood": numero de 0 a 100, "trust": numero de 0 a 100, "ready_to_buy": true ou false}}"""


def finish_session():
    messages = db.get_messages(st.session_state.session_id)
    transcript = "\n".join(
        f"{'Vendedor' if m['role'] == 'seller' else 'Cliente'}: {m['content']}"
        for m in messages
    )
    coach_prompt = f"""Você é um coach de vendas experiente analisando uma simulação de treino.
O cenário do cliente era: {st.session_state.scenario['pitch']}

Analise a transcrição e responda APENAS com um objeto JSON válido, sem markdown:
{{"overall_score": numero de 0 a 100, "summary": "resumo de 1-2 frases", "strengths": ["..."], "improvements": ["..."], "best_moment": "citação literal da melhor fala do vendedor", "missed_moment": "um momento em que perdeu uma oportunidade, e o que poderia ter dito"}}

Seja específico, cite exemplos reais da conversa."""

    feedback = get_feedback(coach_prompt, transcript) or {}
    db.end_session(
        st.session_state.session_id,
        st.session_state.mood,
        st.session_state.trust,
        feedback.get("overall_score", 0),
    )
    db.save_feedback(
        st.session_state.session_id,
        feedback.get("summary", ""),
        feedback.get("strengths", []),
        feedback.get("improvements", []),
        feedback.get("best_moment", ""),
        feedback.get("missed_moment", ""),
    )
    st.session_state.feedback = feedback
    st.session_state.screen = "feedback"


# ---------------------------------------------------------------- SETUP
def render_setup():
    st.title("🤝 Treino de Vendas")
    st.caption("Escolha um perfil de cliente e pratique antes da venda de verdade.")

    for s in db.list_scenarios():
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            col1.markdown(f"**{s['name']}** · _{s['difficulty']}_  \n{s['pitch']}")
            if col2.button("Começar", key=f"start_{s['id']}"):
                start_session(s)
                st.rerun()

    st.divider()
    with st.expander("📊 Histórico de sessões"):
        history = db.get_history()
        if history:
            st.dataframe(history, use_container_width=True, hide_index=True)
        else:
            st.caption("Nenhuma sessão concluída ainda.")


# ---------------------------------------------------------------- CHAT
def render_chat():
    scenario = st.session_state.scenario

    if st.button("← Trocar cenário"):
        st.session_state.screen = "setup"
        st.rerun()

    st.subheader(scenario["name"])

    col1, col2 = st.columns(2)
    col1.progress(st.session_state.mood / 100, text=f"Humor: {st.session_state.mood}")
    col2.progress(st.session_state.trust / 100, text=f"Confiança: {st.session_state.trust}")

    messages = db.get_messages(st.session_state.session_id)
    for m in messages:
        with st.chat_message("user" if m["role"] == "seller" else "assistant"):
            st.write(m["content"])

    prompt = st.chat_input("Digite sua fala de vendedor...")
    if prompt:
        db.add_message(st.session_state.session_id, "seller", prompt)
        st.session_state.api_history.append({"role": "user", "content": prompt})

        system_prompt = build_client_system_prompt(scenario)
        with st.spinner("Cliente está pensando..."):
            result = get_client_reply(system_prompt, st.session_state.api_history)

        reply = result.get("reply", "...")
        mood = int(result.get("mood", st.session_state.mood))
        trust = int(result.get("trust", st.session_state.trust))

        db.add_message(st.session_state.session_id, "client", reply, mood, trust)
        # Guardamos só o texto da fala (não o dict inteiro com mood/trust/ready_to_buy).
        # Reenviar o JSON completo a cada turno inflaria o histórico à toa — a IA
        # já viu mood/trust na resposta anterior e não precisa disso no histórico.
        st.session_state.api_history.append({"role": "assistant", "content": reply})
        st.session_state.mood = max(0, min(100, mood))
        st.session_state.trust = max(0, min(100, trust))
        st.rerun()

    st.divider()
    if st.button("Encerrar conversa e receber feedback", type="primary", use_container_width=True):
        with st.spinner("Analisando a conversa..."):
            finish_session()
        st.rerun()


# ---------------------------------------------------------------- FEEDBACK
def render_feedback():
    fb = st.session_state.feedback or {}

    st.title(f"Nota: {fb.get('overall_score', '—')}/100")
    st.write(fb.get("summary", ""))

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**✅ Pontos fortes**")
        for s in fb.get("strengths", []):
            st.markdown(f"- {s}")
    with col2:
        st.markdown("**⚠️ A melhorar**")
        for s in fb.get("improvements", []):
            st.markdown(f"- {s}")

    if fb.get("best_moment"):
        st.info(f"💬 **Melhor momento:** {fb['best_moment']}")
    if fb.get("missed_moment"):
        st.warning(f"🔍 **Oportunidade perdida:** {fb['missed_moment']}")

    col1, col2 = st.columns(2)
    if col1.button("🔁 Tentar de novo", use_container_width=True):
        start_session(st.session_state.scenario)
        st.rerun()
    if col2.button("Escolher outro cliente", use_container_width=True):
        st.session_state.screen = "setup"
        st.rerun()


# ---------------------------------------------------------------- ROUTER
if st.session_state.screen == "setup":
    render_setup()
elif st.session_state.screen == "chat":
    render_chat()
elif st.session_state.screen == "feedback":
    render_feedback()
