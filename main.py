#!/usr/bin/env python3
"""
EXTREME MODE BOT v3.0
Log Channel Support | Admin Panel | User Auth System
"""

import asyncio
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass
from telethon import TelegramClient
from telethon.network import connection
from aiohttp import web

import config
from handlers import register_handlers
import database as db

# --- WEB SERVER ---
async def handle(request):
    return web.Response(
        text="🔥 EXTREME MODE v3.0 - Admin Panel & Auth System Active"
    )

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', config.PORT)
    await site.start()
    config.logger.info(f"⚡ Web Server - Port {config.PORT}")

# --- MAIN ---
async def main():
    config.logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    config.logger.info("🚀 EXTREME MODE BOT v3.0 Starting...")
    config.logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Initialize Database
    await db.init_db()
    config.logger.info("💾 Database Initialized")

    # --- CLIENT SETUP ---
    # We ONLY start the Bot Client here.
    # User Clients are started dynamically via SessionManager.

    # Validate Config
    if not config.API_ID or not config.API_HASH:
        config.logger.error("❌ MISSING CONFIGURATION!")
        config.logger.error("Please set API_ID and API_HASH in your Environment Variables.")
        config.logger.error("Exiting...")
        return

    bot_client = TelegramClient(
        'bot_session',
        config.API_ID,
        config.API_HASH,
        connection=connection.ConnectionTcpFull,
        use_ipv6=False,
        connection_retries=None,
        flood_sleep_threshold=120,
        request_retries=20,
        auto_reconnect=True
    )
    
    # Start Bot Client
    await bot_client.start(bot_token=config.BOT_TOKEN)
    
    # Register all handlers (Only need bot_client now)
    register_handlers(bot_client)
    
    # Start web server
    asyncio.create_task(start_web_server())
    
    config.logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    config.logger.info("✅ System Online!")
    config.logger.info(f"👑 Admin ID: {config.ADMIN_ID}")
    config.logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Run bot
    await bot_client.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
