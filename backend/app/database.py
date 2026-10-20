import os
from uuid import UUID

import psycopg
from psycopg.rows import dict_row


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL is not configured.")
    return url


def check_database() -> bool:
    try:
        with psycopg.connect(database_url(), connect_timeout=3) as connection:
            connection.execute("SELECT 1")
        return True
    except Exception:
        return False


def ensure_schema(connection: psycopg.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id UUID PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS messages (
            id BIGSERIAL PRIMARY KEY,
            session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            citations JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS messages_session_id_id_idx
            ON messages(session_id, id);
        """
    )


def history(session_id: UUID, limit: int = 10) -> list[tuple[str, str]]:
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        ensure_schema(connection)
        rows = connection.execute(
            "SELECT role, content FROM messages WHERE session_id = %s "
            "ORDER BY id DESC LIMIT %s",
            (session_id, limit),
        ).fetchall()
    return [(row["role"], row["content"]) for row in reversed(rows)]


def save_exchange(
    session_id: UUID, question: str, answer: str, citations: list[dict]
) -> None:
    with psycopg.connect(database_url()) as connection:
        ensure_schema(connection)
        connection.execute(
            "INSERT INTO sessions (id) VALUES (%s) "
            "ON CONFLICT (id) DO UPDATE SET updated_at = now()",
            (session_id,),
        )
        connection.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (%s, 'user', %s)",
            (session_id, question),
        )
        connection.execute(
            "INSERT INTO messages (session_id, role, content, citations) "
            "VALUES (%s, 'assistant', %s, %s)",
            (session_id, answer, psycopg.types.json.Jsonb(citations)),
        )
