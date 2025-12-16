import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import config
import logging

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self):
        self.active_client = None
        self.active_user_id = None
        self.temp_clients = {} # user_id -> client (for login process)
        self.lock = asyncio.Lock()

    async def create_temp_client(self, user_id):
        """Creates a temporary client for login flow"""
        client = TelegramClient(
            StringSession(),
            config.API_ID,
            config.API_HASH,
            device_model="ExtremeBot",
            system_version="Linux",
            app_version="2.0"
        )
        await client.connect()
        self.temp_clients[user_id] = client
        return client

    async def get_temp_client(self, user_id):
        return self.temp_clients.get(user_id)

    async def remove_temp_client(self, user_id):
        if user_id in self.temp_clients:
            await self.temp_clients[user_id].disconnect()
            del self.temp_clients[user_id]

    async def start_user_session(self, session_string, user_id):
        """Starts a client for a user to perform a transfer"""
        async with self.lock:
            if self.active_client:
                if self.active_user_id == user_id:
                    return self.active_client # Already running for this user
                else:
                    raise Exception("Bot is currently busy with another user's transfer. Please wait.")

            client = TelegramClient(
                StringSession(session_string),
                config.API_ID,
                config.API_HASH,
                flood_sleep_threshold=120
            )
            await client.start()
            self.active_client = client
            self.active_user_id = user_id
            return client

    async def stop_user_session(self):
        """Stops the current active session"""
        async with self.lock:
            if self.active_client:
                await self.active_client.disconnect()
                self.active_client = None
                self.active_user_id = None

# Global instance
session_manager = SessionManager()
