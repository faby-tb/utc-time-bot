import sqlite3

conn = sqlite3.connect("settings.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id TEXT PRIMARY KEY,
    enabled INTEGER DEFAULT 0,
    channel_id TEXT,
    last_update TEXT
)
""")
conn.commit()


def set_enabled(guild_id: int, value: bool):
    cursor.execute("""
        INSERT INTO guild_settings (guild_id, enabled)
        VALUES (?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET enabled=excluded.enabled
    """, (str(guild_id), int(value)))
    conn.commit()


def is_enabled(guild_id: int) -> bool:
    cursor.execute("""
        SELECT enabled FROM guild_settings WHERE guild_id=?
    """, (str(guild_id),))
    row = cursor.fetchone()
    return bool(row[0]) if row else False

def set_channel(guild_id: int, channel_id: int):
    cursor.execute("""
        INSERT INTO guild_settings (guild_id, enabled, channel_id)
        VALUES (?, 1, ?)
        ON CONFLICT(guild_id)
        DO UPDATE SET channel_id=excluded.channel_id
    """, (str(guild_id), str(channel_id)))
    conn.commit()


def get_channel(guild_id: int):
    cursor.execute("""
        SELECT channel_id FROM guild_settings WHERE guild_id=?
    """, (str(guild_id),))
    row = cursor.fetchone()
    return int(row[0]) if row and row[0] else None

def set_last_update(guild_id: int, timestamp: str):
    cursor.execute("""
        INSERT INTO guild_settings (guild_id, last_update)
        VALUES (?, ?)
        ON CONFLICT(guild_id)
        DO UPDATE SET last_update=excluded.last_update
    """, (str(guild_id), timestamp))

    conn.commit()

def get_last_update(guild_id: int):
    cursor.execute("""
        SELECT last_update FROM guild_settings WHERE guild_id=?
    """, (str(guild_id),))

    row = cursor.fetchone()
    return row[0] if row else None