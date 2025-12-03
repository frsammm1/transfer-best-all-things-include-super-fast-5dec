#!/usr/bin/env python3
"""
EXTREME MODE BOT v2.0
32MB Chunks × 5 Queue = 160MB Buffer
Complete File Manipulation System
"""

import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.network import connection
from aiohttp import web

from config import (
    API_ID, API_HASH, STRING_SESSION, BOT_TOKEN, PORT, logger
)
from handlers import register_handlers

# --- EXTREME CLIENT SETUP ---
user_client = TelegramClient(
    StringSession(STRING_SESSION), 
    API_ID, 
    API_HASH,
    connection=connection.ConnectionTcpFull,
    use_ipv6=False,
    connection_retries=None,
    flood_sleep_threshold=120,
    request_retries=20,
    auto_reconnect=True
)

bot_client = TelegramClient(
    'bot_session', 
    API_ID, 
    API_HASH,
    connection=connection.ConnectionTcpFull,
    use_ipv6=False,
    connection_retries=None,
    flood_sleep_threshold=120,
    request_retries=20,
    auto_reconnect=True
)

# --- WEB SERVER ---
async def handle(request):
    return web.Response(
        text="🔥 EXTREME MODE v2.0 - 32MB×5 Active | File Manipulation Enabled"
    )

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"⚡ EXTREME MODE Web Server - Port {PORT}")

# --- MAIN ---
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("🚀 EXTREME MODE BOT v2.0 Starting...")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("⚡ Config: 32MB chunks × 5 queue = 160MB buffer")
    logger.info("📝 Features: File manipulation enabled")
    logger.info("🔥 Maximum speed + Smart controls")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("⚠️  WARNING: High RAM usage - Monitor closely!")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Start clients
    user_client.start()
    bot_client.start(bot_token=BOT_TOKEN)
    
    # Register all handlers
    register_handlers(user_client, bot_client)
    
    # Start web server
    loop.create_task(start_web_server())
    
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("✅ EXTREME MODE Active!")
    logger.info("🔥 Bot is ready for transfers!")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Run bot
    bot_client.run_until_disconnected()
