import os
import asyncio
import logging
import time
import math
import re
import mimetypes
from telethon import TelegramClient, events, utils, errors
from telethon.sessions import StringSession
from telethon.network import connection
from telethon.tl.types import (
    DocumentAttributeFilename, 
    DocumentAttributeVideo, 
    DocumentAttributeAudio,
    MessageMediaWebPage
)
from aiohttp import web

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH")
STRING_SESSION = os.environ.get("STRING_SESSION") 
BOT_TOKEN = os.environ.get("BOT_TOKEN")           
PORT = int(os.environ.get("PORT", 8080))

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- EXTREME CLIENT SETUP (32MB CHUNKS - MAXIMUM PERFORMANCE) ---
user_client = TelegramClient(
    StringSession(STRING_SESSION), 
    API_ID, 
    API_HASH,
    connection=connection.ConnectionTcpFull,
    use_ipv6=False,
    connection_retries=None,
    flood_sleep_threshold=120,  # 60 -> 120 (aggressive)
    request_retries=20,  # 10 -> 20 (more retries)
    auto_reconnect=True,
    recv_buffer=512 * 1024,  # 512KB receive buffer (max)
    connection_pool_size=15  # More connections
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
    auto_reconnect=True,
    recv_buffer=512 * 1024,
    connection_pool_size=15
)

# --- GLOBAL STATE ---
pending_requests = {} 
current_task = None
is_running = False
status_message = None
last_update_time = 0

# --- WEB SERVER ---
async def handle(request):
    return web.Response(text="🔥 EXTREME MODE - 32MB Chunks Active - Ultra Speed Unlocked")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"⚡ EXTREME MODE Web Server - Port {PORT}")

# --- HELPER FUNCTIONS ---
def human_readable_size(size):
    if not size: return "0B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0: return f"{size:.2f}{unit}"
        size /= 1024.0
    return f"{size:.2f}TB"

def time_formatter(seconds):
    if seconds is None or seconds < 0: return "..."
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0: return f"{hours}h {minutes}m {seconds}s"
    return f"{minutes}m {seconds}s"

# --- EXTREME PROGRESS CALLBACK (Less Frequent) ---
async def progress_callback(current, total, start_time, file_name):
    global last_update_time, status_message
    now = time.time()
    
    # Update every 10 seconds (reduce API calls)
    if now - last_update_time < 10: return 
    last_update_time = now
    
    percentage = current * 100 / total if total > 0 else 0
    time_diff = now - start_time
    speed = current / time_diff if time_diff > 0 else 0
    eta = (total - current) / speed if speed > 0 else 0
    
    filled = math.floor(percentage / 10)
    bar = "█" * filled + "░" * (10 - filled)
    
    try:
        await status_message.edit(
            f"🚀 **EXTREME MODE (32MB)**\n"
            f"📂 `{file_name}`\n"
            f"**{bar} {round(percentage, 1)}%**\n"
            f"⚡ `{human_readable_size(speed)}/s` | ⏳ `{time_formatter(eta)}`\n"
            f"💾 `{human_readable_size(current)} / {human_readable_size(total)}`"
        )
    except Exception: pass

# --- EXTREME BUFFERED STREAM (32MB CHUNKS × 6 QUEUE) ---
class ExtremeBufferedStream:
    def __init__(self, client, location, file_size, file_name, start_time):
        self.client = client
        self.location = location
        self.file_size = file_size
        self.name = file_name
        self.start_time = start_time
        self.current_bytes = 0
        
        # 🔥 EXTREME SETTINGS
        self.chunk_size = 32 * 1024 * 1024  # 32MB chunks
        self.queue = asyncio.Queue(maxsize=6)  # 192MB buffer (32MB × 6)
        
        self.downloader_task = asyncio.create_task(self._worker())
        self.buffer = b""
        self.closed = False
        
        logger.info(f"🚀 EXTREME Stream: 32MB chunks, 192MB buffer for {file_name}")

    async def _worker(self):
        try:
            async for chunk in self.client.iter_download(
                self.location, 
                chunk_size=self.chunk_size,
                request_size=self.chunk_size  # Match for efficiency
            ):
                if self.closed:
                    break
                await self.queue.put(chunk)
            await self.queue.put(None) 
        except Exception as e:
            logger.error(f"⚠️ Stream Worker Error: {e}")
            await self.queue.put(None)

    def __len__(self):
        return self.file_size

    async def read(self, size=-1):
        if self.closed:
            return b""
            
        if size == -1: 
            size = self.chunk_size
            
        while len(self.buffer) < size:
            chunk = await self.queue.get()
            if chunk is None: 
                if self.current_bytes < self.file_size:
                    logger.warning(f"⚠️ Incomplete: {self.current_bytes}/{self.file_size}")
                self.closed = True
                break
            self.buffer += chunk
            self.current_bytes += len(chunk)
            
            # Fire-and-forget progress update
            asyncio.create_task(progress_callback(
                self.current_bytes, 
                self.file_size, 
                self.start_time, 
                self.name
            ))
            
        data = self.buffer[:size]
        self.buffer = self.buffer[size:]
        return data

    async def close(self):
        self.closed = True
        if self.downloader_task and not self.downloader_task.done():
            self.downloader_task.cancel()
            try:
                await self.downloader_task
            except asyncio.CancelledError:
                pass

# --- SMART FORMAT ENFORCER ---
def get_target_info(message):
    """
    Video -> MP4, Image -> JPG, Doc -> PDF
    """
    original_name = "Unknown_File"
    target_mime = "application/octet-stream"
    force_video = False
    
    if isinstance(message.media, MessageMediaWebPage):
        return None, None, False

    if message.file:
        original_mime = message.file.mime_type
        if message.file.name:
            original_name = message.file.name
        else:
            ext = mimetypes.guess_extension(original_mime) or ""
            original_name = f"File_{message.id}{ext}"
    else:
        original_mime = "image/jpeg"
        original_name = f"Image_{message.id}.jpg"

    base_name = os.path.splitext(original_name)[0]
    
    # VIDEO (MKV, AVI, WEBM -> MP4)
    if "video" in original_mime or original_name.lower().endswith(('.mkv', '.avi', '.webm', '.mov', '.flv')):
        final_name = base_name + ".mp4"
        target_mime = "video/mp4"
        force_video = True
        
    # IMAGE (PNG, WEBP -> JPG)
    elif "image" in original_mime:
        final_name = base_name + ".jpg"
        target_mime = "image/jpeg"
        force_video = False
        
    # PDF
    elif "pdf" in original_mime or original_name.lower().endswith('.pdf'):
        final_name = base_name + ".pdf"
        target_mime = "application/pdf"
        force_video = False
        
    # OTHERS
    else:
        final_name = original_name
        target_mime = original_mime
        force_video = False
        
    return final_name, target_mime, force_video

# --- EXTREME TRANSFER PROCESS ---
async def transfer_process(event, source_id, dest_id, start_msg, end_msg):
    global is_running, status_message
    
    status_message = await event.respond(
        f"🚀 **EXTREME MODE ACTIVATED!**\n"
        f"⚡ Chunk: 32MB | Buffer: 192MB\n"
        f"🔥 Max Speed Unlocked!\n"
        f"Source: `{source_id}`"
    )
    total_processed = 0
    total_size = 0
    overall_start = time.time()
    
    try:
        async for message in user_client.iter_messages(
            source_id, 
            min_id=start_msg-1, 
            max_id=end_msg+1, 
            reverse=True
        ):
            if not is_running:
                await status_message.edit("🛑 **Stopped by User!**")
                break

            if getattr(message, 'action', None): 
                continue

            retries = 4  # Extra retry for extreme mode
            success = False
            stream_file = None
            
            while retries > 0 and not success:
                try:
                    # Refresh message to avoid expired references
                    fresh_msg = await user_client.get_messages(source_id, ids=message.id)
                    if not fresh_msg: 
                        break 

                    file_name, mime_type, is_video_mode = get_target_info(fresh_msg)
                    
                    # Handle text/empty messages
                    if not file_name:
                        if fresh_msg.text:
                            await bot_client.send_message(dest_id, fresh_msg.text)
                            success = True
                        else:
                            success = True
                        continue

                    await status_message.edit(
                        f"🚀 **EXTREME TRANSFER**\n"
                        f"📂 `{file_name}`\n"
                        f"💪 Attempt: {5-retries}/4"
                    )

                    start_time = time.time()
                    
                    # Prepare attributes
                    attributes = []
                    attributes.append(DocumentAttributeFilename(file_name=file_name))
                    
                    if hasattr(fresh_msg, 'document') and fresh_msg.document:
                        for attr in fresh_msg.document.attributes:
                            if isinstance(attr, DocumentAttributeVideo):
                                attributes.append(DocumentAttributeVideo(
                                    duration=attr.duration,
                                    w=attr.w,
                                    h=attr.h,
                                    supports_streaming=True
                                ))

                    # Download thumbnail (small, won't affect RAM much)
                    thumb = None
                    try:
                        thumb = await user_client.download_media(fresh_msg, thumb=-1)
                    except:
                        pass
                    
                    # Prepare media object
                    media_obj = (fresh_msg.media.document 
                                if hasattr(fresh_msg.media, 'document') 
                                else fresh_msg.media.photo)
                    
                    # 🔥 CREATE EXTREME STREAM
                    stream_file = ExtremeBufferedStream(
                        user_client, 
                        media_obj,
                        fresh_msg.file.size,
                        file_name,
                        start_time
                    )
                    
                    # 🔥 UPLOAD WITH 32MB PARTS
                    await bot_client.send_file(
                        dest_id,
                        file=stream_file,
                        caption=fresh_msg.text or "",
                        attributes=attributes,
                        thumb=thumb,
                        supports_streaming=True,
                        file_size=fresh_msg.file.size,
                        force_document=not is_video_mode,
                        part_size_kb=32768  # 32MB upload parts (EXTREME)
                    )
                    
                    # Cleanup
                    if thumb and os.path.exists(thumb): 
                        os.remove(thumb)
                    
                    success = True
                    elapsed = time.time() - start_time
                    speed = fresh_msg.file.size / elapsed / (1024*1024) if elapsed > 0 else 0
                    total_size += fresh_msg.file.size
                    
                    await status_message.edit(
                        f"✅ **EXTREME SENT:** `{file_name}`\n"
                        f"⚡ Speed: `{speed:.1f} MB/s`\n"
                        f"📦 Files: {total_processed + 1}"
                    )

                except (errors.FileReferenceExpiredError, errors.MediaEmptyError):
                    logger.warning(f"🔄 Ref expired on {message.id}, refreshing...")
                    retries -= 1
                    await asyncio.sleep(2)
                    continue 
                    
                except errors.FloodWaitError as e:
                    logger.warning(f"⏳ FloodWait {e.seconds}s")
                    await status_message.edit(
                        f"⏳ **Cooling Down...**\n"
                        f"Waiting: `{e.seconds}s`"
                    )
                    await asyncio.sleep(e.seconds)
                
                except MemoryError:
                    logger.error("💥 RAM LIMIT HIT! Reducing to safe mode...")
                    await status_message.edit(
                        f"⚠️ **RAM Overflow Detected!**\n"
                        f"File too large for extreme mode.\n"
                        f"Skipping: `{file_name}`"
                    )
                    retries = 0  # Stop trying this file
                
                except Exception as e:
                    logger.error(f"❌ Failed {message.id}: {e}")
                    retries -= 1
                    if retries > 0:
                        await asyncio.sleep(3)
                
                finally:
                    # CRITICAL: Always close stream
                    if stream_file:
                        await stream_file.close()

            if not success:
                try: 
                    await bot_client.send_message(
                        event.chat_id, 
                        f"❌ **FAILED:** `{message.id}` after 4 attempts."
                    )
                except: 
                    pass
            
            total_processed += 1
            
            # Memory management: pause every 5 files
            if total_processed % 5 == 0:
                await asyncio.sleep(2)  # Let garbage collector work

        if is_running:
            overall_time = time.time() - overall_start
            avg_speed = total_size / overall_time / (1024*1024) if overall_time > 0 else 0
            
            await status_message.edit(
                f"🏁 **EXTREME MODE COMPLETE!**\n"
                f"✅ Files: `{total_processed}`\n"
                f"📦 Size: `{human_readable_size(total_size)}`\n"
                f"⚡ Avg Speed: `{avg_speed:.1f} MB/s`\n"
                f"⏱️ Time: `{time_formatter(overall_time)}`"
            )

    except Exception as e:
        await status_message.edit(f"💥 **Critical Error:** {e}")
        logger.error(f"Transfer crashed: {e}")
    finally:
        is_running = False

# --- COMMANDS ---
@bot_client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await event.respond(
        "🚀 **EXTREME MODE BOT**\n"
        "⚡ 32MB Chunks | 192MB Buffer\n"
        "🔥 Maximum Speed Unlocked!\n\n"
        "Usage: `/clone Source Dest`\n"
        "⚠️ Warning: High RAM usage!"
    )

@bot_client.on(events.NewMessage(pattern='/clone'))
async def clone_init(event):
    global is_running
    if is_running: 
        return await event.respond("⚠️ Already running a task...")
    try:
        args = event.text.split()
        pending_requests[event.chat_id] = {
            'source': int(args[1]), 
            'dest': int(args[2])
        }
        await event.respond(
            "✅ **EXTREME MODE Ready!**\n"
            "Send message range link:\n"
            "`https://t.me/c/xxx/10 - https://t.me/c/xxx/20`"
        )
    except: 
        await event.respond("❌ Usage: `/clone -100xxx -100yyy`")

@bot_client.on(events.NewMessage())
async def range_listener(event):
    global current_task, is_running
    if event.chat_id not in pending_requests or "t.me" not in event.text: 
        return
    try:
        links = event.text.strip().split("-")
        msg1 = int(links[0].strip().split("/")[-1])
        msg2 = int(links[1].strip().split("/")[-1])
        if msg1 > msg2: 
            msg1, msg2 = msg2, msg1
        
        data = pending_requests.pop(event.chat_id)
        is_running = True
        current_task = asyncio.create_task(
            transfer_process(event, data['source'], data['dest'], msg1, msg2)
        )
    except Exception as e: 
        await event.respond(f"❌ Error: {e}")

@bot_client.on(events.NewMessage(pattern='/stop'))
async def stop_handler(event):
    global is_running, current_task
    is_running = False
    if current_task: 
        current_task.cancel()
    await event.respond("🛑 **EXTREME MODE Stopped!**")

@bot_client.on(events.NewMessage(pattern='/stats'))
async def stats_handler(event):
    await event.respond(
        f"📊 **EXTREME MODE Stats**\n"
        f"⚡ Chunk Size: 32MB\n"
        f"💾 Buffer: 192MB (6 chunks)\n"
        f"📤 Upload Parts: 32MB\n"
        f"🔄 Max Retries: 20\n"
        f"⏱️ Update Interval: 10s\n"
        f"🚀 Status: {'Running' if is_running else 'Idle'}"
    )

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    
    logger.info("🚀 Starting EXTREME MODE Bot...")
    logger.info("⚡ Config: 32MB chunks × 6 queue = 192MB buffer")
    logger.info("⚠️ WARNING: High RAM usage - Monitor closely!")
    
    user_client.start()
    loop.create_task(start_web_server())
    bot_client.start(bot_token=BOT_TOKEN)
    
    logger.info("🔥 EXTREME MODE Active - Maximum Speed Unlocked!")
    bot_client.run_until_disconnected()
