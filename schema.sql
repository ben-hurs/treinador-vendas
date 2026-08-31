-- Perfis de cliente disponíveis para o treino
CREATE TABLE IF NOT EXISTS scenarios (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    difficulty TEXT,
    pitch TEXT,
    system_prompt TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cada tentativa de treino (uma conversa completa)
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    final_mood INTEGER,
    final_trust INTEGER,
    overall_score INTEGER
);

-- Cada fala da conversa (vendedor ou cliente)
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL CHECK (role IN ('seller', 'client')),
    content TEXT NOT NULL,
    mood INTEGER,
    trust INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Feedback do "coach" gerado ao final de cada sessão
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL UNIQUE REFERENCES sessions(id),
    summary TEXT,
    strengths TEXT,      -- lista em JSON
    improvements TEXT,   -- lista em JSON
    best_moment TEXT,
    missed_moment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
