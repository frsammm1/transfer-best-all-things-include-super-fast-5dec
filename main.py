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

# --- CLIENT SETUP (RENDER OPTIMIZED - IPv4 Only) ---
user_client = TelegramClient(
    StringSession(STRING_SESSION), 
    API_ID, 
    API_HASH,
    connection=connection.ConnectionTcpFull,
    use_ipv6=False,
    connection_retries=None, 
    flood_sleep_threshold=60,
    request_retries=10,
    auto_reconnect=True,
    timeout=30  # Faster timeout
)

bot_client = TelegramClient(
    'bot_session', 
    API_ID, 
    API_HASH,
    connection=connection.ConnectionTcpFull,
    use_ipv6=False,
    connection_retries=None, 
    flood_sleep_threshold=60,
    request_retries=10,
    auto_reconnect=True,
    timeout=30
)

# --- GLOBAL STATE ---
pending_requests = {} 
manipulation_settings = {}
current_task = None
is_running = False
status_message = None
last_update_time = 0

# --- WEB SERVER ---
async def handle(request):
    return web.Response(text="🔥 Ultra File Manipulator Bot v2.0 - Status: Active ⚡")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"🌐 Web server started on port {PORT}")

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

# --- PROGRESS CALLBACK (Optimized) ---
async def progress_callback(current, total, start_time, file_name):
    global last_update_time, status_message
    now = time.time()
    
    # Update every 7 seconds (reduced API calls = faster)
    if now - last_update_time < 7: return 
    last_update_time = now
    
    percentage = current * 100 / total if total > 0 else 0
    time_diff = now - start_time
    speed = current / time_diff if time_diff > 0 else 0
    eta = (total - current) / speed if speed > 0 else 0
    
    filled = math.floor(percentage / 10)
    bar = "█" * filled + "▒" * (10 - filled)
    
    try:
        await status_message.edit(
            f"⚡ **Ultra Transfer Engine**\n"
            f"📂 `{file_name[:35]}...`\n"
            f"**{bar}** `{round(percentage, 1)}%`\n"
            f"🚀 **Speed:** `{human_readable_size(speed)}/s`\n"
            f"⏳ **ETA:** `{time_formatter(eta)}`\n"
            f"💾 `{human_readable_size(current)}` / `{human_readable_size(total)}`"
        )
    except Exception: pass

# --- ULTRA BUFFERED STREAM (SPEED OPTIMIZED) ---
class UltraBufferedStream:
    def __init__(self, client, location, file_size, file_name, start_time):
        self.client = client
        self.location = location
        self.file_size = file_size
        self.name = file_name
        self.start_time = start_time
        self.current_bytes = 0
        self.chunk_size = 10 * 1024 * 1024  # 10MB chunks (increased from 8MB)
        self.queue = asyncio.Queue(maxsize=8)  # Larger buffer (was 5)
        self.downloader_task = asyncio.create_task(self._worker())
        self.buffer = b""

    async def _worker(self):
        try:
            async for chunk in self.client.iter_download(self.location, chunk_size=self.chunk_size):
                await self.queue.put(chunk)
            await self.queue.put(None) 
        except Exception as e:
            logger.error(f"Stream Worker Error: {e}")
            await self.queue.put(None)

    def __len__(self):
        return self.file_size

    async def read(self, size=-1):
        if size == -1: size = self.chunk_size
        while len(self.buffer) < size:
            chunk = await self.queue.get()
            if chunk is None: 
                if self.current_bytes < self.file_size:
                    raise errors.RpcCallFailError("Incomplete Stream")
                break
            self.buffer += chunk
            self.current_bytes += len(chunk)
            asyncio.create_task(progress_callback(self.current_bytes, self.file_size, self.start_time, self.name))
        data = self.buffer[:size]
        self.buffer = self.buffer[size:]
        return data

# --- CAPTION MANIPULATION ---
def process_caption(original_caption, settings):
    """
    Caption me Find/Replace aur Extra text add karta hai
    """
    caption = original_caption or ""
    
    # Find & Replace in Caption
    if settings.get('find_caption') and settings.get('replace_caption'):
        caption = caption.replace(settings['find_caption'], settings['replace_caption'])
    
    # Add Extra Caption
    if settings.get('extra_caption'):
        if caption:
            caption += f"\n\n{settings['extra_caption']}"
        else:
            caption = settings['extra_caption']
    
    return caption

# --- FILENAME MANIPULATION ---
def get_target_info(message, settings={}):
    """
    File ka naya naam aur type decide karega + Find/Replace support
    """
    original_name = "Unknown_File"
    target_mime = "application/octet-stream"
    force_video = False
    
    # 1. WebPage Handling
    if isinstance(message.media, MessageMediaWebPage):
        return None, None, False

    # 2. Get Original Info
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

    # 3. FILENAME MANIPULATION (Find & Replace)
    base_name = os.path.splitext(original_name)[0]
    original_ext = os.path.splitext(original_name)[1]
    
    # Apply Find & Replace on filename
    if settings.get('find_filename') and settings.get('replace_filename'):
        base_name = base_name.replace(settings['find_filename'], settings['replace_filename'])
    
    # 4. ENFORCE FORMATS
    # CASE A: VIDEO (MKV, AVI, WEBM -> MP4)
    if "video" in original_mime or original_name.lower().endswith(('.mkv', '.avi', '.webm', '.mov', '.flv', '.m4v')):
        final_name = base_name + ".mp4"
        target_mime = "video/mp4"
        force_video = True
        
    # CASE B: IMAGE (PNG, WEBP -> JPG)
    elif "image" in original_mime:
        final_name = base_name + ".jpg"
        target_mime = "image/jpeg"
        force_video = False
        
    # CASE C: PDF (Maintain PDF)
    elif "pdf" in original_mime or original_name.lower().endswith('.pdf'):
        final_name = base_name + ".pdf"
        target_mime = "application/pdf"
        force_video = False
        
    # CASE D: AUDIO
    elif "audio" in original_mime or original_name.lower().endswith(('.mp3', '.m4a', '.flac', '.wav')):
        final_name = base_name + original_ext
        target_mime = original_mime
        force_video = False
        
    # CASE E: OTHERS (Keep original extension)
    else:
        final_name = base_name + original_ext
        target_mime = original_mime
        force_video = False
        
    return final_name, target_mime, force_video

# --- TRANSFER PROCESS (OPTIMIZED) ---
async def transfer_process(event, source_id, dest_id, start_msg, end_msg, settings={}):
    global is_running, status_message
    
    status_message = await event.respond(
        f"🔥 **Ultra Transfer Engine Started!**\n\n"
        f"📡 **Source:** `{source_id}`\n"
        f"📤 **Destination:** `{dest_id}`\n"
        f"📊 **Range:** `{start_msg}` → `{end_msg}`\n"
        f"⚙️ **Settings:** {'Applied ✅' if settings else 'Default'}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    total_processed = 0
    failed_messages = []
    start_transfer_time = time.time()
    
    try:
        async for message in user_client.iter_messages(source_id, min_id=start_msg-1, max_id=end_msg+1, reverse=True):
            if not is_running:
                await status_message.edit("🛑 **Transfer Stopped by User!**")
                break

            if getattr(message, 'action', None): continue

            # --- RETRY LOOP (No Skip) ---
            retries = 3
            success = False
            
            while retries > 0 and not success:
                try:
                    # 1. REFRESH MESSAGE (Fixes Expired Reference)
                    fresh_msg = await user_client.get_messages(source_id, ids=message.id)
                    if not fresh_msg: break 

                    # 2. GET MANIPULATED FILE INFO
                    file_name, mime_type, is_video_mode = get_target_info(fresh_msg, settings)
                    
                    # Handle Text Only Messages
                    if not file_name:
                        if fresh_msg.text:
                            new_caption = process_caption(fresh_msg.text, settings)
                            await bot_client.send_message(dest_id, new_caption)
                            success = True
                        else:
                            success = True
                        continue

                    await status_message.edit(
                        f"⚡ **Processing...**\n"
                        f"📂 `{file_name[:40]}...`\n"
                        f"🔄 Attempt: **{4-retries}/3**"
                    )

                    start_time = time.time()
                    
                    # 3. PREPARE ATTRIBUTES
                    attributes = []
                    attributes.append(DocumentAttributeFilename(file_name=file_name))
                    
                    # Preserve video metadata
                    if hasattr(fresh_msg, 'document') and fresh_msg.document:
                        for attr in fresh_msg.document.attributes:
                            if isinstance(attr, DocumentAttributeVideo):
                                attributes.append(DocumentAttributeVideo(
                                    duration=attr.duration,
                                    w=attr.w,
                                    h=attr.h,
                                    supports_streaming=True
                                ))
                            elif isinstance(attr, DocumentAttributeAudio):
                                attributes.append(attr)

                    # 4. STREAM & UPLOAD (OPTIMIZED)
                    thumb = None
                    try:
                        thumb = await user_client.download_media(fresh_msg, thumb=-1)
                    except: pass
                    
                    media_obj = fresh_msg.media.document if hasattr(fresh_msg.media, 'document') else fresh_msg.media.photo
                    
                    stream_file = UltraBufferedStream(
                        user_client, 
                        media_obj,
                        fresh_msg.file.size,
                        file_name,
                        start_time
                    )
                    
                    # Process Caption
                    new_caption = process_caption(fresh_msg.text, settings)
                    
                    await bot_client.send_file(
                        dest_id,
                        file=stream_file,
                        caption=new_caption,
                        attributes=attributes,
                        thumb=thumb,
                        supports_streaming=True,
                        file_size=fresh_msg.file.size,
                        force_document=not is_video_mode,
                        part_size_kb=10240  # Increased from 8192 (10MB parts)
                    )
                    
                    if thumb and os.path.exists(thumb): 
                        try: os.remove(thumb)
                        except: pass
                    
                    success = True
                    total_processed += 1
                    
                    await status_message.edit(
                        f"✅ **Transferred:** `{file_name[:35]}...`\n"
                        f"📊 **Progress:** `{total_processed}` files done"
                    )

                except (errors.FileReferenceExpiredError, errors.MediaEmptyError):
                    logger.warning(f"⚠️ Ref Expired on {message.id}, refreshing...")
                    retries -= 1
                    await asyncio.sleep(2)
                    continue 
                    
                except errors.FloodWaitError as e:
                    logger.warning(f"⏸️ FloodWait {e.seconds}s")
                    await status_message.edit(f"⏸️ **Rate Limited!** Waiting `{e.seconds}s`...")
                    await asyncio.sleep(e.seconds)
                
                except Exception as e:
                    logger.error(f"❌ Failed {message.id}: {e}")
                    retries -= 1
                    if retries > 0:
                        await asyncio.sleep(3)

            if not success:
                failed_messages.append(message.id)
                try: 
                    await bot_client.send_message(
                        event.chat_id, 
                        f"❌ **FAILED:** Message ID `{message.id}` - Skipped after 3 attempts."
                    )
                except: pass

        # Final Report
        if is_running:
            total_time = time.time() - start_transfer_time
            await status_message.edit(
                f"🎉 **Transfer Complete!**\n\n"
                f"✅ **Success:** `{total_processed}` files\n"
                f"❌ **Failed:** `{len(failed_messages)}` files\n"
                f"⏱️ **Time:** `{time_formatter(total_time)}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{'🔴 Failed IDs: ' + str(failed_messages) if failed_messages else '🟢 All files transferred successfully!'}"
            )

    except Exception as e:
        await status_message.edit(f"💥 **Critical Error:** `{e}`")
        logger.error(f"Transfer Process Error: {e}")
    finally:
        is_running = False

# --- COMMANDS ---
@bot_client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await event.respond(
        "🔥 **Ultra File Manipulator Bot v2.0**\n\n"
        "**Features:**\n"
        "⚡ Lightning fast transfers\n"
        "📝 Filename Find & Replace\n"
        "💬 Caption manipulation\n"
        "🎬 Auto MP4 conversion\n"
        "🖼️ Auto JPG conversion\n\n"
        "**Commands:**\n"
        "`/clone` - Start transfer\n"
        "`/stop` - Stop current task\n"
        "`/help` - Detailed guide\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Made with ❤️ by Ultra Dev"
    )

@bot_client.on(events.NewMessage(pattern='/help'))
async def help_handler(event):
    await event.respond(
        "📖 **How to Use:**\n\n"
        "**Step 1:** Send command\n"
        "`/clone -100source -100dest`\n\n"
        "**Step 2:** Send message range\n"
        "`https://t.me/c/xxx/10 - https://t.me/c/xxx/50`\n\n"
        "**Step 3 (Optional):** Manipulation settings\n"
        "```\n"
        "FIND_FILE: BluRay\n"
        "REPLACE_FILE: WebRip\n"
        "FIND_CAP: @OldChannel\n"
        "REPLACE_CAP: @NewChannel\n"
        "EXTRA_CAP: 🔥 Join @MyChannel\n"
        "```\n"
        "Or send `/skip` for no changes\n\n"
        "**Example:**\n"
        "Input: `Movie.BluRay.mkv`\n"
        "Output: `Movie.WebRip.mp4`"
    )

@bot_client.on(events.NewMessage(pattern='/clone'))
async def clone_init(event):
    global is_running
    if is_running: 
        return await event.respond("⚠️ **Already busy!** Use `/stop` first.")
    
    try:
        args = event.text.split()
        if len(args) < 3:
            return await event.respond(
                "❌ **Invalid format!**\n\n"
                "**Usage:**\n"
                "`/clone -100source -100dest`\n\n"
                "**Example:**\n"
                "`/clone -1001234567890 -1009876543210`"
            )
        
        user_id = event.chat_id
        pending_requests[user_id] = {
            'source': int(args[1]), 
            'dest': int(args[2]),
            'step': 'range'
        }
        
        await event.respond(
            "✅ **Source & Destination Set!**\n\n"
            "📍 **Step 1:** Send message range\n"
            "Format: `link1 - link2`\n\n"
            "**Example:**\n"
            "`https://t.me/c/1234/10 - https://t.me/c/1234/100`"
        )
    except ValueError:
        await event.respond("❌ Invalid chat IDs! Use numeric format like `-1001234567890`")
    except Exception as e:
        await event.respond(f"❌ Error: `{e}`")

@bot_client.on(events.NewMessage())
async def input_listener(event):
    global current_task, is_running
    user_id = event.chat_id
    
    if user_id not in pending_requests: return
    
    data = pending_requests[user_id]
    text = event.text.strip()
    
    # STEP 1: Range Detection
    if data.get('step') == 'range' and "t.me" in text:
        try:
            links = text.split("-")
            msg1 = int(links[0].strip().split("/")[-1])
            msg2 = int(links[1].strip().split("/")[-1])
            if msg1 > msg2: msg1, msg2 = msg2, msg1
            
            data['start_msg'] = msg1
            data['end_msg'] = msg2
            data['step'] = 'settings'
            
            await event.respond(
                "✅ **Range Set!**\n\n"
                f"📊 **Messages:** `{msg1}` → `{msg2}` ({msg2-msg1+1} files)\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "📝 **Step 2 (Optional):** Manipulation Settings\n\n"
                "**Format:**\n"
                "```\n"
                "FIND_FILE: old_text\n"
                "REPLACE_FILE: new_text\n"
                "FIND_CAP: old_caption\n"
                "REPLACE_CAP: new_caption\n"
                "EXTRA_CAP: Your extra text\n"
                "```\n\n"
                "**Or send `/skip` to proceed without changes**"
            )
        except Exception as e:
            await event.respond(f"❌ Invalid range format!\nError: `{e}`")
        return
    
    # STEP 2: Settings or Skip
    if data.get('step') == 'settings':
        settings = {}
        
        if text != '/skip':
            for line in text.split('\n'):
                line = line.strip()
                if line.startswith('FIND_FILE:'):
                    settings['find_filename'] = line.replace('FIND_FILE:', '').strip()
                elif line.startswith('REPLACE_FILE:'):
                    settings['replace_filename'] = line.replace('REPLACE_FILE:', '').strip()
                elif line.startswith('FIND_CAP:'):
                    settings['find_caption'] = line.replace('FIND_CAP:', '').strip()
                elif line.startswith('REPLACE_CAP:'):
                    settings['replace_caption'] = line.replace('REPLACE_CAP:', '').strip()
                elif line.startswith('EXTRA_CAP:'):
                    settings['extra_caption'] = line.replace('EXTRA_CAP:', '').strip()
            
            settings_summary = []
            if settings.get('find_filename'):
                settings_summary.append(f"📝 Filename: `{settings['find_filename']}` → `{settings.get('replace_filename', 'N/A')}`")
            if settings.get('find_caption'):
                settings_summary.append(f"💬 Caption: `{settings['find_caption']}` → `{settings.get('replace_caption', 'N/A')}`")
            if settings.get('extra_caption'):
                settings_summary.append(f"➕ Extra: `{settings['extra_caption'][:30]}...`")
            
            settings_text = "\n".join(settings_summary) if settings_summary else "Default (No changes)"
            
            await event.respond(
                f"🚀 **Starting Transfer...**\n\n"
                f"⚙️ **Settings Applied:**\n{settings_text}"
            )
        else:
            await event.respond("🚀 **Starting Transfer (No changes)...**")
        
        is_running = True
        manipulation_settings[user_id] = settings
        
        current_task = asyncio.create_task(
            transfer_process(
                event, 
                data['source'], 
                data['dest'], 
                data['start_msg'], 
                data['end_msg'],
                settings
            )
        )
        
        pending_requests.pop(user_id)
        return

@bot_client.on(events.NewMessage(pattern='/stop'))
async def stop_handler(event):
    global is_running, current_task
    
    if not is_running:
        return await event.respond("⚠️ No active transfer to stop!")
    
    is_running = False
    if current_task: 
        current_task.cancel()
    
    await event.respond(
        "🛑 **Transfer Stopped!**\n\n"
        "You can start a new transfer with `/clone`"
    )

# --- MAIN ---
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    
    logger.info("🔥 Starting Ultra File Manipulator Bot v2.0...")
    
    user_client.start()
    logger.info("✅ User Client Connected")
    
    loop.create_task(start_web_server())
    
    bot_client.start(bot_token=BOT_TOKEN)
    logger.info("✅ Bot Client Connected")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("🟢 Bot is Running! Press Ctrl+C to stop")
    
    bot_client.run_until_disconnected()
