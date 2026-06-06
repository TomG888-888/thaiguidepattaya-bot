import os
import sqlite3
from contextlib import closing


DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.db")


def get_connection():
    return sqlite3.connect(DATABASE_PATH)


def init_db():
    with closing(get_connection()) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_peer_id_id
            ON messages (peer_id, id)
            """
        )
        connection.commit()


def add_message(peer_id, role, content, limit=20):
    with closing(get_connection()) as connection:
        connection.execute(
            """
            INSERT INTO messages (peer_id, role, content)
            VALUES (?, ?, ?)
            """,
            (peer_id, role, content),
        )
        connection.execute(
            """
            DELETE FROM messages
            WHERE peer_id = ?
              AND id NOT IN (
                  SELECT id
                  FROM messages
                  WHERE peer_id = ?
                  ORDER BY id DESC
                  LIMIT ?
              )
            """,
            (peer_id, peer_id, limit),
        )
        connection.commit()


def get_message_count(peer_id):
    with closing(get_connection()) as connection:
        cursor = connection.execute(
            "SELECT COUNT(*) FROM messages WHERE peer_id = ?",
            (peer_id,),
        )
        return cursor.fetchone()[0]


def get_recent_messages(peer_id, limit=20):
    with closing(get_connection()) as connection:
        cursor = connection.execute(
            """
            SELECT role, content
            FROM (
                SELECT id, role, content
                FROM messages
                WHERE peer_id = ?
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id ASC
            """,
            (peer_id, limit),
        )
        return [{"role": role, "content": content} for role, content in cursor.fetchall()]
