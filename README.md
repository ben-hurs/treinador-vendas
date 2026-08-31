# Treino de Vendas — versão local

App de simulação de vendas com IA: você conversa com um "cliente virtual" e recebe
feedback no final. Tudo em Python + SQLite, pra rodar 100% na sua máquina.

## Estrutura

```
sales_trainer_local/
├── app.py             # app principal (Streamlit) — a interface
├── db.py               # todo o acesso ao banco (SQLite)
├── claude_client.py     # chamadas pra API da Anthropic
├── personas.py           # perfis de cliente (edite aqui pra adicionar novos)
├── schema.sql             # estrutura das tabelas
├── requirements.txt
└── .env.example
```

## Passo a passo

### 1. Pré-requisitos
- Python 3.10 ou mais novo instalado (`python3 --version` pra conferir)
- Uma chave de API da Anthropic (console.anthropic.com → API Keys)

### 2. Criar ambiente virtual

```bash
cd sales_trainer_local
python3 -m venv venv

# ativar (Mac/Linux)
source venv/bin/activate

# ativar (Windows)
venv\Scripts\activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar a chave de API

```bash
cp .env.example .env
```

Abra o arquivo `.env` e cole sua chave:
```
ANTHROPIC_API_KEY=sk-ant-...
```

### 5. Rodar

```bash
streamlit run app.py
```

Vai abrir automaticamente no navegador em `http://localhost:8501`.

Na primeira execução, o `db.py` cria o arquivo `sales_trainer.db` (SQLite) sozinho
e já popula com os 4 perfis de cliente definidos em `personas.py`.

## Explorando o banco com SQL

Já que você curte SQL, dá pra abrir o banco direto e consultar:

```bash
sqlite3 sales_trainer.db
```

Alguns exemplos:

```sql
-- suas últimas sessões e notas
SELECT sc.name, s.overall_score, s.started_at
FROM sessions s JOIN scenarios sc ON s.scenario_id = sc.id
WHERE s.ended_at IS NOT NULL
ORDER BY s.started_at DESC;

-- evolução média de nota por cliente
SELECT sc.name, ROUND(AVG(s.overall_score), 1) AS media, COUNT(*) AS tentativas
FROM sessions s JOIN scenarios sc ON s.scenario_id = sc.id
WHERE s.overall_score IS NOT NULL
GROUP BY sc.name
ORDER BY media DESC;
```

## Adicionando novos perfis de cliente

Edite `personas.py` e acrescente um novo dict na lista `SCENARIOS`. Na próxima
vez que rodar o app, ele é inserido automaticamente no banco (a função
`seed_scenarios` usa `INSERT OR IGNORE`, então não duplica).

## Otimizações de token aplicadas

- **Prompt caching**: o system prompt de cada persona é enviado com
  `cache_control: ephemeral`. Como ele se repete em toda mensagem da mesma
  conversa, a Anthropic cobra bem menos (e responde mais rápido) nas
  chamadas seguintes, em vez de reprocessar o prompt inteiro a cada turno.
- **Histórico sem redundância**: antes, cada resposta da IA (um JSON com
  `reply`/`mood`/`trust`/`ready_to_buy`) era guardada inteira e reenviada em
  todo turno seguinte. Agora só o texto da fala (`reply`) entra no
  histórico — o resto era peso morto que a IA não precisa reler.
- **Histórico limitado**: conversas muito longas agora enviam só as últimas
  ~6 trocas de mensagem pra API (o histórico completo continua salvo no
  banco e é usado no feedback final, então não perde nada de análise).
- **Modelo por tarefa**: as falas do cliente (alto volume — uma chamada por
  mensagem do vendedor) usam Claude Haiku 4.5, bem mais barato. O feedback
  final (uma chamada por sessão) continua no Sonnet, que entrega uma
  análise mais rica — vale o custo porque roda só 1x.
- **Retry com backoff**: chamadas com erro passageiro (rate limit / servidor
  sobrecarregado) tentam de novo automaticamente, o que fica mais comum
  quando várias pessoas usam o app ao mesmo tempo.

## Deploy em produção (Streamlit Community Cloud) — grátis

O Streamlit Community Cloud é a forma mais barata de colocar isso no ar: é
grátis para apps públicos, já resolve HTTPS/domínio, e aguenta bem 10+
pessoas simultâneas nesse tipo de app (uso leve de CPU, o gargalo é a API da
Anthropic, não o servidor).

### 1. Subir o código pro GitHub
Suba esta pasta num repositório (o `.gitignore` já exclui `venv/`, `.env` e o
banco local — não é pra versionar isso).

### 2. Criar o app no Streamlit Cloud
Em [share.streamlit.io](https://share.streamlit.io) → **New app** → aponte
pro repositório, branch e o arquivo `app.py`.

### 3. Configurar a chave de API como secret
Em **Settings → Secrets** do app, cole:
```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```
(É por isso que `claude_client.py` já lê `st.secrets` primeiro — em produção
não se usa mais o `.env`.)

### 4. Deploy
Clique em **Deploy**. Em ~1-2 minutos o app está no ar com uma URL pública.

### ⚠️ Limitação importante do SQLite nesse tipo de deploy
O Streamlit Community Cloud usa armazenamento **efêmero**: o arquivo
`sales_trainer.db` persiste enquanto o app está rodando, mas é **apagado**
sempre que o app reinicia (reboot automático, novo deploy, etc.) — ou seja,
o histórico de sessões não é permanente. Pra até 10 pessoas testando/
treinando, isso na prática funciona bem no dia a dia (o banco só reseta em
reinícios pouco frequentes). Se você precisar que o histórico nunca se
perca, me avisa que trocamos o SQLite por um banco externo persistente
(ex.: Turso/libSQL — SQLite gerenciado, quase zero mudança de código — ou
Postgres via Supabase/Railway, ambos com camada grátis).

### Sobre aguentar 10+ pessoas ao mesmo tempo
- Cada usuário tem sua própria `st.session_state`, então as conversas não se
  misturam entre pessoas.
- O SQLite agora roda em modo WAL com timeout de espera, o que evita o erro
  "database is locked" quando várias pessoas gravam mensagens ao mesmo
  tempo.
- O limite real de concorrência é o **rate limit da sua conta na Anthropic**
  (tokens/minuto e requisições/minuto do seu tier). Para 10 pessoas
  conversando ao mesmo tempo isso raramente é um problema, mas se notar
  erros de rate limit vale checar o tier da sua chave em
  console.anthropic.com → Settings → Limits.

## Próximo passo: escalar mais

Se um dia isso crescer além de dezenas de usuários simultâneos ou precisar
de histórico 100% permanente, me chama que a gente troca o SQLite por
Postgres, containeriza com Docker e sobe num serviço como Railway, Render ou
AWS — sem precisar reescrever a lógica do app, só a camada `db.py` muda.
