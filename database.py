import os
import sqlite3
from contextlib import closing


DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.db")
LEAD_STATUSES = ("new", "active", "booked", "lost")
LEAD_STAGES = ("new", "qualified", "offer_sent", "booked", "lost")


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
                        CHECK (status IN ('new', 'active', 'booked', 'lost')),
                    stage TEXT NOT NULL DEFAULT 'new'
                        CHECK (stage IN ('new', 'qualified', 'offer_sent', 'booked', 'lost'))
                )
                """
            )
            cursor.execute(
                """
                ALTER TABLE leads
                ADD COLUMN IF NOT EXISTS stage TEXT NOT NULL DEFAULT 'new'
                    CHECK (stage IN ('new', 'qualified', 'offer_sent', 'booked', 'lost'))
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_events (
                    event_key TEXT PRIMARY KEY,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tours (
                    tour_key TEXT PRIMARY KEY,
                    is_published BOOLEAN NOT NULL DEFAULT FALSE,
                    published_at TIMESTAMPTZ,
                    vk_product_url TEXT
                )
                """
            )
            cursor.execute(
                """
                ALTER TABLE tours
                ADD COLUMN IF NOT EXISTS is_published BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
            cursor.execute(
                """
                ALTER TABLE tours
                ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ
                """
            )
            cursor.execute(
                """
                ALTER TABLE tours
                ADD COLUMN IF NOT EXISTS vk_product_url TEXT
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
                    CHECK (status IN ('new', 'active', 'booked', 'lost')),
                stage TEXT NOT NULL DEFAULT 'new'
                    CHECK (stage IN ('new', 'qualified', 'offer_sent', 'booked', 'lost'))
            )
            """
        )
        cursor = connection.execute("PRAGMA table_info(leads)")
        columns = {row[1] for row in cursor.fetchall()}
        if "stage" not in columns:
            connection.execute(
                """
                ALTER TABLE leads
                ADD COLUMN stage TEXT NOT NULL DEFAULT 'new'
                    CHECK (stage IN ('new', 'qualified', 'offer_sent', 'booked', 'lost'))
                """
            )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_events (
                event_key TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tours (
                tour_key TEXT PRIMARY KEY,
                is_published INTEGER NOT NULL DEFAULT 0,
                published_at TIMESTAMP,
                vk_product_url TEXT
            )
            """
        )
        cursor = connection.execute("PRAGMA table_info(tours)")
        columns = {row[1] for row in cursor.fetchall()}
        if "is_published" not in columns:
            connection.execute(
                """
                ALTER TABLE tours
                ADD COLUMN is_published INTEGER NOT NULL DEFAULT 0
                """
            )
        if "published_at" not in columns:
            connection.execute(
                """
                ALTER TABLE tours
                ADD COLUMN published_at TIMESTAMP
                """
            )
        if "vk_product_url" not in columns:
            connection.execute(
                """
                ALTER TABLE tours
                ADD COLUMN vk_product_url TEXT
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


def mark_event_processed(event_key):
    param = placeholder()

    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        if is_postgres():
            cursor.execute(
                """
                INSERT INTO processed_events (event_key)
                VALUES (%s)
                ON CONFLICT (event_key) DO NOTHING
                """,
                (event_key,),
            )
        else:
            cursor.execute(
                f"""
                INSERT OR IGNORE INTO processed_events (event_key)
                VALUES ({param})
                """,
                (event_key,),
            )

        connection.commit()
        inserted = cursor.rowcount > 0
        cursor.close()

        return inserted


def get_setting(key):
    param = placeholder()

    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
            SELECT value
            FROM settings
            WHERE key = {param}
            """,
            (key,),
        )
        row = cursor.fetchone()
        cursor.close()

        if not row:
            return None

        return row[0]


def set_setting(key, value):
    param = placeholder()

    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        if is_postgres():
            cursor.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key)
                DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                """,
                (key, value),
            )
        else:
            cursor.execute(
                f"""
                INSERT INTO settings (key, value, updated_at)
                VALUES ({param}, {param}, CURRENT_TIMESTAMP)
                ON CONFLICT(key)
                DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
                """,
                (key, value),
            )
        connection.commit()
        cursor.close()


def mark_tour_published(tour_key):
    param = placeholder()

    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        if is_postgres():
            cursor.execute(
                """
                INSERT INTO tours (tour_key, is_published, published_at)
                VALUES (%s, TRUE, CURRENT_TIMESTAMP)
                ON CONFLICT (tour_key)
                DO UPDATE SET is_published = TRUE, published_at = CURRENT_TIMESTAMP
                """,
                (tour_key,),
            )
        else:
            cursor.execute(
                f"""
                INSERT INTO tours (tour_key, is_published, published_at)
                VALUES ({param}, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(tour_key)
                DO UPDATE SET is_published = 1, published_at = CURRENT_TIMESTAMP
                """,
                (tour_key,),
            )
        connection.commit()
        cursor.close()


def unmark_tour_published(tour_key):
    param = placeholder()

    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        if is_postgres():
            cursor.execute(
                """
                INSERT INTO tours (tour_key, is_published, published_at)
                VALUES (%s, FALSE, NULL)
                ON CONFLICT (tour_key)
                DO UPDATE SET is_published = FALSE, published_at = NULL
                """,
                (tour_key,),
            )
        else:
            cursor.execute(
                f"""
                INSERT INTO tours (tour_key, is_published, published_at)
                VALUES ({param}, 0, NULL)
                ON CONFLICT(tour_key)
                DO UPDATE SET is_published = 0, published_at = NULL
                """,
                (tour_key,),
            )
        connection.commit()
        cursor.close()


def set_tour_vk_product_url(tour_key, url):
    param = placeholder()

    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        if is_postgres():
            cursor.execute(
                """
                INSERT INTO tours (tour_key, vk_product_url)
                VALUES (%s, %s)
                ON CONFLICT (tour_key)
                DO UPDATE SET vk_product_url = EXCLUDED.vk_product_url
                """,
                (tour_key, url),
            )
        else:
            cursor.execute(
                f"""
                INSERT INTO tours (tour_key, vk_product_url)
                VALUES ({param}, {param})
                ON CONFLICT(tour_key)
                DO UPDATE SET vk_product_url = excluded.vk_product_url
                """,
                (tour_key, url),
            )
        connection.commit()
        cursor.close()


def get_tour_vk_product_url(tour_key):
    param = placeholder()

    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT vk_product_url FROM tours WHERE tour_key = {param}",
            (tour_key,),
        )
        row = cursor.fetchone()
        cursor.close()

        return row[0] if row and row[0] else ""


def get_published_tours():
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT tour_key, published_at
            FROM tours
            WHERE is_published = TRUE
            ORDER BY published_at DESC, tour_key ASC
            """
            if is_postgres()
            else """
            SELECT tour_key, published_at
            FROM tours
            WHERE is_published = 1
            ORDER BY published_at DESC, tour_key ASC
            """
        )
        rows = cursor.fetchall()
        cursor.close()

        return [
            {
                "tour_key": tour_key,
                "published_at": published_at,
            }
            for tour_key, published_at in rows
        ]


def get_published_tour_keys():
    return {tour["tour_key"] for tour in get_published_tours()}


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
                INSERT INTO leads (peer_id, name, status, stage)
                VALUES (%s, %s, 'new', 'new')
                ON CONFLICT (peer_id) DO NOTHING
                """,
                (peer_id, name),
            )
        else:
            cursor.execute(
                f"""
                INSERT OR IGNORE INTO leads (peer_id, name, status, stage)
                VALUES ({param}, {param}, 'new', 'new')
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
            SELECT stage, COUNT(*)
            FROM leads
            GROUP BY stage
            """
        )
        counts = {stage: 0 for stage in LEAD_STAGES}
        counts.update(dict(cursor.fetchall()))
        cursor.close()

        return counts


def get_leads():
    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT peer_id, first_contact, stage
            FROM leads
            ORDER BY first_contact DESC
            """
        )
        leads = [
            {
                "peer_id": peer_id,
                "first_contact": str(first_contact),
                "status": stage,
            }
            for peer_id, first_contact, stage in cursor.fetchall()
        ]
        cursor.close()

        return leads


def get_lead_stage(peer_id):
    param = placeholder()

    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
            SELECT stage
            FROM leads
            WHERE peer_id = {param}
            """,
            (peer_id,),
        )
        row = cursor.fetchone()
        cursor.close()

        if not row:
            return None

        return row[0]


def update_lead_status(peer_id, status):
    if status not in LEAD_STATUSES:
        return False

    param = placeholder()
    stage = status if status in LEAD_STAGES else "new"

    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
            UPDATE leads
            SET status = {param}, stage = {param}
            WHERE peer_id = {param}
            """,
            (status, stage, peer_id),
        )
        connection.commit()
        updated = cursor.rowcount > 0
        cursor.close()

        return updated


def update_lead_stage(peer_id, stage):
    if stage not in LEAD_STAGES:
        return False

    param = placeholder()

    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
            UPDATE leads
            SET stage = {param}
            WHERE peer_id = {param}
              AND stage NOT IN ('booked', 'lost')
            """,
            (stage, peer_id),
        )
        connection.commit()
        updated = cursor.rowcount > 0
        cursor.close()

        return updated
