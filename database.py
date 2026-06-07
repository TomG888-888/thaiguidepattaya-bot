import os
import sqlite3
from contextlib import closing


DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.db")
LEAD_STATUSES = ("new", "active", "booked", "lost")


def is_postgres():
    return bool(DATABASE_URL)


def get_connection():
    if is_postgres():
        import psycopg2

        return psycopg2.connect(DATABASE_URL)

    return sqlite3.connect(DATABASE_PATH)


def placeholder():
    return "%s" if is_postgres() else "?"


def init_db():
    if is_postgres():
        init_postgres_db()
    else:
        init_sqlite_db()


def init_postgres_db():
    with closing(get_connection()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id BIGSERIAL PRIMARY KEY,
                    peer_id BIGINT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_peer_id_id
                ON messages (peer_id, id)
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS leads (
                    peer_id BIGINT PRIMARY KEY,
                    name TEXT,
                    first_contact TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL DEFAULT 'new'
                        CHECK (status IN ('new', 'active', 'booked', 'lost'))
                )
                """
            )
        connection.commit()


def init_sqlite_db():
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
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                peer_id INTEGER PRIMARY KEY,
                name TEXT,
                first_contact TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'new'
                    CHECK (status IN ('new', 'active', 'booked', 'lost'))
            )
            """
        )
        connection.commit()


def add_message(peer_id, role, content, limit=20):
    param = placeholder()

    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
            INSERT INTO messages (peer_id, role, content)
            VALUES ({param}, {param}, {param})
            """,
            (peer_id, role, content),
        )
        cursor.execute(
            f"""
            DELETE FROM messages
            WHERE peer_id = {param}
              AND id NOT IN (
                  SELECT id
                  FROM messages
                  WHERE peer_id = {param}
                  ORDER BY id DESC
                  LIMIT {param}
              )
            """,
            (peer_id, peer_id, limit),
        )
        connection.commit()
        cursor.close()


def get_message_count(peer_id):
    param = placeholder()

    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT COUNT(*) FROM messages WHERE peer_id = {param}",
            (peer_id,),
        )
        count = cursor.fetchone()[0]
        cursor.close()

        return count


def get_recent_messages(peer_id, limit=20):
    param = placeholder()

    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
            SELECT role, content
            FROM (
                SELECT id, role, content
                FROM messages
                WHERE peer_id = {param}
                ORDER BY id DESC
                LIMIT {param}
            ) recent_messages
            ORDER BY id ASC
            """,
            (peer_id, limit),
        )
        messages = [
            {"role": role, "content": content}
            for role, content in cursor.fetchall()
        ]
        cursor.close()

        return messages


def create_lead(peer_id, name=None):
    param = placeholder()

    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        if is_postgres():
            cursor.execute(
                """
                INSERT INTO leads (peer_id, name, status)
                VALUES (%s, %s, 'new')
                ON CONFLICT (peer_id) DO NOTHING
                """,
                (peer_id, name),
            )
        else:
            cursor.execute(
                f"""
                INSERT OR IGNORE INTO leads (peer_id, name, status)
                VALUES ({param}, {param}, 'new')
                """,
                (peer_id, name),
            )
        connection.commit()
        cursor.close()


def get_lead_status_counts():
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT status, COUNT(*)
            FROM leads
            GROUP BY status
            """
        )
        counts = {status: 0 for status in LEAD_STATUSES}
        counts.update(dict(cursor.fetchall()))
        cursor.close()

        return counts


def get_leads():
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT peer_id, first_contact, status
            FROM leads
            ORDER BY first_contact DESC
            """
        )
        leads = [
            {
                "peer_id": peer_id,
                "first_contact": str(first_contact),
                "status": status,
            }
            for peer_id, first_contact, status in cursor.fetchall()
        ]
        cursor.close()

        return leads


def update_lead_status(peer_id, status):
    if status not in LEAD_STATUSES:
        return False

    param = placeholder()

    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
            UPDATE leads
            SET status = {param}
            WHERE peer_id = {param}
            """,
            (status, peer_id),
        )
        connection.commit()
        updated = cursor.rowcount > 0
        cursor.close()

        return updated
