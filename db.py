import sqlite3

conn = sqlite3.connect("settings.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id TEXT PRIMARY KEY,
    enabled INTEGER DEFAULT 0
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