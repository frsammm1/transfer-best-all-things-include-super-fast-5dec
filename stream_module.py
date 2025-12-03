import asyncio
import time
from config import CHUNK_SIZE, QUEUE_SIZE, logger, last_update_time, status_message, UPDATE_INTERVAL
from utils import human_readable_size, time_formatter
import math

async def progress_callback(current, total, start_time, file_name, status_msg):
    """Update progress with reduced frequency"""
    global last_update_time
    now = time.time()
    
    # Update every UPDATE_INTERVAL seconds
    if now - last_update_time < UPDATE_INTERVAL: 
        return 
    last_update_time = now
    
    percentage = current * 100 / total if total > 0 else 0
    time_diff = now - start_time
    speed = current / time_diff if time_diff > 0 else 0
    eta = (total - current) / speed if speed > 0 else 0
    
    filled = math.floor(percentage / 10)
    bar = "█" * filled + "░" * (10 - filled)
    
    try:
        await status_msg.edit(
            f"🚀 **EXTREME MODE (32MB × 5)**\n"
            f"📂 `{file_name[:40]}...`\n"
            f"**{bar} {round(percentage, 1)}%**\n"
            f"⚡ `{human_readable_size(speed)}/s` | ⏳ `{time_formatter(eta)}`\n"
            f"💾 `{human_readable_size(current)} / {human_readable_size(total)}`"
        )
    except Exception:
        pass

class ExtremeBufferedStream:
    """
    Extreme performance streaming with 32MB chunks and 5-queue buffer (160MB)
    """
    def __init__(self, client, location, file_size, file_name, start_time, status_msg):
        self.client = client
        self.location = location
        self.file_size = file_size
        self.name = file_name
        self.start_time = start_time
        self.status_msg = status_msg
        self.current_bytes = 0
        
        # EXTREME SETTINGS
        self.chunk_size = CHUNK_SIZE
        self.queue = asyncio.Queue(maxsize=QUEUE_SIZE)  # 160MB buffer
        
        self.downloader_task = asyncio.create_task(self._worker())
        self.buffer = b""
        self.closed = False
        
        logger.info(f"🚀 EXTREME Stream: 32MB chunks, 160MB buffer for {file_name}")

    async def _worker(self):
        """Background worker to download chunks"""
        try:
            async for chunk in self.client.iter_download(
                self.location, 
                chunk_size=self.chunk_size,
                request_size=self.chunk_size
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
        """Read data from stream"""
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
                self.name,
                self.status_msg
            ))
            
        data = self.buffer[:size]
        self.buffer = self.buffer[size:]
        return data

    async def close(self):
        """Clean shutdown of stream"""
        self.closed = True
        if self.downloader_task and not self.downloader_task.done():
            self.downloader_task.cancel()
            try:
                await self.downloader_task
            except asyncio.CancelledError:
                pass
