import asyncio
import time
import math
import config
from utils import human_readable_size, time_formatter

async def progress_callback(current, total, start_time, file_name, status_msg):
    """Update progress with reduced frequency"""
    now = time.time()
    
    # Update every UPDATE_INTERVAL seconds
    if now - config.last_update_time < config.UPDATE_INTERVAL: 
        return 
    config.last_update_time = now
    
    percentage = current * 100 / total if total > 0 else 0
    time_diff = now - start_time
    speed = current / time_diff if time_diff > 0 else 0
    eta = (total - current) / speed if speed > 0 else 0
    
    filled = math.floor(percentage / 10)
    bar = "█" * filled + "░" * (10 - filled)
    
    try:
        await status_msg.edit(
            f"📦 **Transferring...**\n"
            f"📂 `{file_name[:30]}...`\n"
            f"**{bar} {round(percentage, 1)}%**\n"
            f"⚡ `{human_readable_size(speed)}/s` | ETA: `{time_formatter(eta)}`\n"
            f"💾 `{human_readable_size(current)} / {human_readable_size(total)}`"
        )
    except Exception as e:
        config.logger.debug(f"Progress update failed: {e}")

class ByteLimitedQueue:
    """
    A Queue that respects a byte limit instead of item limit.
    This solves the issue where small chunks (128KB) fill the item limit
    causing the downloader to stall, while the uploader starves waiting for
    large parts (16MB).
    """
    def __init__(self, max_bytes):
        self.max_bytes = max_bytes
        self.current_bytes = 0
        self.queue = asyncio.Queue() # Unbounded items, bounded by logic below
        self.condition = asyncio.Condition()

    async def put(self, item):
        async with self.condition:
            # If item is None (EOF), we always accept it
            if item is None:
                await self.queue.put(None)
                return

            size = len(item)
            # Wait if adding this item would exceed max_bytes
            # But always allow at least one item to avoid deadlock if item > max_bytes
            while self.current_bytes + size > self.max_bytes and self.current_bytes > 0:
                await self.condition.wait()

            await self.queue.put(item)
            self.current_bytes += size
            self.condition.notify_all()

    async def get(self):
        item = await self.queue.get()

        if item is None:
            # Put it back for other consumers if any (though we only have one)
            # Actually, standard pattern is to return None and not decrement
            return None

        async with self.condition:
            self.current_bytes -= len(item)
            self.condition.notify_all()

        return item

    def empty(self):
        return self.queue.empty()

    def get_nowait(self):
        return self.queue.get_nowait()

class SplitFile:
    """Wrapper to split a large stream into virtual parts"""
    def __init__(self, stream, max_size):
        self.stream = stream
        self.max_size = max_size
        self.current_pos = 0
        self.closed = False

    def __len__(self):
        return self.max_size

    async def read(self, size=-1):
        if self.closed:
            return b""

        remaining = self.max_size - self.current_pos
        if remaining <= 0:
            return b""

        if size == -1 or size > remaining:
            size = remaining

        chunk = await self.stream.read(size)
        if not chunk:
            return b""

        self.current_pos += len(chunk)
        return chunk

    async def close(self):
        self.closed = True
        # Note: We do NOT close the parent stream here

class ExtremeBufferedStream:
    """
    Optimized streaming using ByteLimitedQueue.
    Buffer size is controlled by RAM usage (e.g. 100MB) regardless of chunk count.
    Solves cross-DC 128KB chunk starvation issues.
    """
    def __init__(self, client, location, file_size, file_name, start_time, status_msg):
        self.client = client
        self.location = location
        self.file_size = file_size
        self.name = file_name
        self.start_time = start_time
        self.status_msg = status_msg
        self.current_bytes = 0
        
        # Optimized settings
        self.chunk_size = config.CHUNK_SIZE
        # Use config defined byte limit
        self.queue = ByteLimitedQueue(max_bytes=config.MAX_RAM_BUFFER)
        
        self.downloader_task = None
        self.buffer = b""
        self.closed = False
        self._started = False
        
        config.logger.info(f"📦 Stream initialized: {file_name} ({human_readable_size(file_size)})")

    async def _start_download(self):
        """Start the download worker"""
        if self._started:
            return
        self._started = True
        self.downloader_task = asyncio.create_task(self._worker())

    async def _worker(self):
        """Background worker to download chunks"""
        try:
            config.logger.info(f"📥 Starting download: {self.name}")
            async for chunk in self.client.iter_download(
                self.location, 
                chunk_size=self.chunk_size,
                request_size=self.chunk_size
            ):
                if self.closed:
                    config.logger.info("Download worker: closed flag detected")
                    break
                    
                await self.queue.put(chunk)
                
            # Signal end of stream
            await self.queue.put(None)
            config.logger.info(f"✅ Download complete: {self.name}")
            
        except asyncio.CancelledError:
            config.logger.info("Download worker cancelled")
            await self.queue.put(None)
            
        except Exception as e:
            config.logger.error(f"⚠️ Download error: {e}")
            await self.queue.put(None)

    def __len__(self):
        return self.file_size

    async def read(self, size=-1):
        """Read data from stream"""
        # Start download on first read
        if not self._started:
            await self._start_download()
        
        if self.closed:
            return b""
            
        if size == -1: 
            size = self.chunk_size
            
        # Fill buffer to requested size
        while len(self.buffer) < size and not self.closed:
            try:
                # Wait for data (increased timeout for large files/slow network)
                chunk = await asyncio.wait_for(self.queue.get(), timeout=60.0)
                
                if chunk is None:
                    # End of stream
                    if self.current_bytes < self.file_size:
                        config.logger.warning(
                            f"⚠️ Incomplete transfer: {self.current_bytes}/{self.file_size} bytes"
                        )
                    self.closed = True
                    break
                
                self.buffer += chunk
                self.current_bytes += len(chunk)
                
                # Update progress (fire-and-forget)
                asyncio.create_task(progress_callback(
                    self.current_bytes, 
                    self.file_size, 
                    self.start_time, 
                    self.name,
                    self.status_msg
                ))
                
            except asyncio.TimeoutError:
                config.logger.error("❌ Download timeout")
                self.closed = True
                break
            except Exception as e:
                config.logger.error(f"Read error: {e}")
                self.closed = True
                break
            
        # Return requested data
        data = self.buffer[:size]
        self.buffer = self.buffer[size:]
        return data

    async def close(self):
        """Clean shutdown of stream"""
        if self.closed:
            return
            
        config.logger.info(f"🔒 Closing stream: {self.name}")
        self.closed = True
        
        # Cancel download task
        if self.downloader_task and not self.downloader_task.done():
            self.downloader_task.cancel()
            try:
                await asyncio.wait_for(self.downloader_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        
        # Clear buffer
        self.buffer = b""
        
        # Drain queue
        while not self.queue.empty():
            try:
                await self.queue.get()
            except:
                break
        
        config.logger.info(f"✅ Stream closed: {self.name}")
