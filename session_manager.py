import asyncio
import os
import shutil
from telethon import TelegramClient
from telethon.sessions import StringSession
import config

class SessionManager:
    def __init__(self):
        self.active_client = None
        self.active_user_id = None
        self.temp_clients = {} # user_id -> client
        # Fix: Do not create asyncio.Lock() here because there is no loop yet
        self._lock = None

        # Ensure sessions directory exists (even if we use StringSession for temps, we might need it later)
        os.makedirs('sessions', exist_ok=True)

    @property
    def lock(self):
        """Lazy initialization of the lock to ensure it's created in a loop"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def create_temp_client(self, user_id):
        """Create a temporary client for login process using StringSession"""
        # Using StringSession allows us to easily save it to DB later
        session = StringSession()
        client = TelegramClient(session, config.API_ID, config.API_HASH)
        await client.connect()
        self.temp_clients[user_id] = client
        return client

    async def get_temp_client(self, user_id):
        return self.temp_clients.get(user_id)

    async def remove_temp_client(self, user_id):
        if user_id in self.temp_clients:
            client = self.temp_clients[user_id]
            await client.disconnect()
            del self.temp_clients[user_id]

    async def start_user_session(self, string_session, user_id):
        """Start a user client for transfer - EXCLUSIVE LOCK"""
        # Wait for lock (only one transfer at a time)
        await self.lock.acquire()

        try:
            client = TelegramClient(StringSession(string_session), config.API_ID, config.API_HASH)
            await client.connect()

            if not await client.is_user_authorized():
                self.lock.release()
                raise Exception("Session invalid/expired")

            self.active_client = client
            self.active_user_id = user_id
            return client

        except Exception as e:
            if self.lock.locked():
                self.lock.release()
            raise e

    async def stop_user_session(self):
        """Stop current transfer session and release lock"""
        if self.active_client:
            await self.active_client.disconnect()
            self.active_client = None
            self.active_user_id = None

        if self.lock.locked():
            self.lock.release()

# Global instance
session_manager = SessionManager()
