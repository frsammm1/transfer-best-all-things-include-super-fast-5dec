import aiosqlite
import time
import os
import logging

DB_PATH = "bot_data.db"
logger = logging.getLogger(__name__)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                phone TEXT,
                session_string TEXT,
                validity_expiry REAL,
                joined_date REAL,
                is_admin INTEGER DEFAULT 0
            )
        """)
        # Config table for dynamic settings (log channel, etc)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.commit()

async def add_user(user_id, phone=None, session_string=None, validity_duration=0):
    expiry = time.time() + validity_duration if validity_duration else 0
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users (user_id, phone, session_string, validity_expiry, joined_date, is_admin)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (user_id, phone, session_string, expiry, time.time()))
        await db.commit()

async def update_user_session(user_id, session_string, phone):
    async with aiosqlite.connect(DB_PATH) as db:
        # Check if user exists first to decide between update or insert (upsert logic)
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()

        if row:
            await db.execute("""
                UPDATE users SET session_string = ?, phone = ? WHERE user_id = ?
            """, (session_string, phone, user_id))
        else:
            # If user doesn't exist (e.g. Admin first login), insert them
            # Default validity to 0 (expired) unless they are admin, but Admin bypasses check in handlers.
            # We set joined_date to now.
            await db.execute("""
                INSERT INTO users (user_id, phone, session_string, validity_expiry, joined_date, is_admin)
                VALUES (?, ?, ?, 0, ?, 0)
            """, (user_id, phone, session_string, time.time()))

        await db.commit()

async def update_validity(user_id, duration):
    """Extend validity for a user. Duration in seconds."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Get current expiry
        cursor = await db.execute("SELECT validity_expiry FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()

        current_expiry = row[0] if row else 0
        now = time.time()

        # If expired or new, start from now. If active, add to existing.
        if current_expiry < now:
            new_expiry = now + duration
        else:
            new_expiry = current_expiry + duration

        await db.execute("""
            INSERT OR REPLACE INTO users (user_id, validity_expiry, joined_date, is_admin)
            VALUES (?, ?, COALESCE((SELECT joined_date FROM users WHERE user_id=?), ?), 0)
        """, (user_id, new_expiry, user_id, now))
        await db.commit()
        return new_expiry

async def check_user(user_id):
    """Returns (is_valid, session_string, phone)"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT validity_expiry, session_string, phone FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()

        if not row:
            return False, None, None

        expiry, session, phone = row
        if expiry > time.time():
            return True, session, phone
        return False, session, phone

async def revoke_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id, validity_expiry, phone FROM users")
        return await cursor.fetchall()

async def set_config(key, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, str(value)))
        await db.commit()

async def get_config(key):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else None
