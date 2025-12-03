import asyncio
import time
import os
from telethon import errors
from telethon.tl.types import (
    DocumentAttributeFilename, 
    DocumentAttributeVideo, 
    DocumentAttributeAudio
)
from config import (
    logger, is_running, UPLOAD_PART_SIZE, 
    MAX_RETRIES, active_sessions
)
from utils import (
    human_readable_size, time_formatter, 
    get_target_info, apply_filename_manipulations,
    apply_caption_manipulations, sanitize_filename
)
from stream import ExtremeBufferedStream
from keyboards import get_progress_keyboard

async def transfer_process(event, user_client, bot_client, source_id, dest_id, start_msg, end_msg, session_id):
    """Main transfer process with all features"""
    global is_running
    
    settings = active_sessions.get(session_id, {}).get('settings', {})
    
    status_message = await event.respond(
        f"🚀 **EXTREME MODE ACTIVATED!**\n"
        f"⚡ Chunk: 32MB | Buffer: 160MB (5×)\n"
        f"🔥 Max Speed Unlocked!\n"
        f"📍 Source: `{source_id}` → Dest: `{dest_id}`",
        buttons=get_progress_keyboard()
    )
    
    total_processed = 0
    total_size = 0
    total_skipped = 0
    overall_start = time.time()
    
    try:
        async for message in user_client.iter_messages(
            source_id, 
            min_id=start_msg-1, 
            max_id=end_msg+1, 
            reverse=True
        ):
            if not is_running:
                await status_message.edit(
                    "🛑 **Transfer Stopped by User!**\n"
                    f"✅ Processed: {total_processed}\n"
                    f"⏭️ Skipped: {total_skipped}"
                )
                break

            # Skip service messages
            if getattr(message, 'action', None): 
                continue

            retries = MAX_RETRIES
            success = False
            stream_file = None
            
            while retries > 0 and not success:
                try:
                    # Refresh message to avoid expired references
                    fresh_msg = await user_client.get_messages(source_id, ids=message.id)
                    if not fresh_msg: 
                        break 

                    # Handle text-only messages
                    if not fresh_msg.media or not fresh_msg.file:
                        if fresh_msg.text:
                            modified_text = apply_caption_manipulations(fresh_msg.text, settings)
                            await bot_client.send_message(dest_id, modified_text)
                            success = True
                        else:
                            success = True
                        continue

                    # Get file info with smart format detection
                    file_name, mime_type, is_video_mode = get_target_info(fresh_msg)
                    
                    if not file_name:
                        success = True
                        continue
                    
                    # Apply filename manipulations
                    file_name = apply_filename_manipulations(file_name, settings)
                    file_name = sanitize_filename(file_name)

                    await status_message.edit(
                        f"🚀 **EXTREME TRANSFER**\n"
                        f"📂 `{file_name[:40]}...`\n"
                        f"💪 Attempt: {MAX_RETRIES - retries + 1}/{MAX_RETRIES}\n"
                        f"📊 Progress: {total_processed}/{end_msg - start_msg + 1}",
                        buttons=get_progress_keyboard()
                    )

                    start_time = time.time()
                    
                    # Prepare attributes
                    attributes = [DocumentAttributeFilename(file_name=file_name)]
                    
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

                    # Download thumbnail
                    thumb = None
                    try:
                        thumb = await user_client.download_media(fresh_msg, thumb=-1)
                    except:
                        pass
                    
                    # Prepare media object
                    media_obj = (fresh_msg.media.document 
                                if hasattr(fresh_msg.media, 'document') 
                                else fresh_msg.media.photo)
                    
                    # CREATE EXTREME STREAM
                    stream_file = ExtremeBufferedStream(
                        user_client, 
                        media_obj,
                        fresh_msg.file.size,
                        file_name,
                        start_time,
                        status_message
                    )
                    
                    # Apply caption manipulations
                    modified_caption = apply_caption_manipulations(fresh_msg.text, settings)
                    
                    # UPLOAD WITH EXTREME SETTINGS
                    await bot_client.send_file(
                        dest_id,
                        file=stream_file,
                        caption=modified_caption,
                        attributes=attributes,
                        thumb=thumb,
                        supports_streaming=True,
                        file_size=fresh_msg.file.size,
                        force_document=not is_video_mode,
                        part_size_kb=UPLOAD_PART_SIZE
                    )
                    
                    # Cleanup thumbnail
                    if thumb and os.path.exists(thumb): 
                        os.remove(thumb)
                    
                    success = True
                    elapsed = time.time() - start_time
                    speed = fresh_msg.file.size / elapsed / (1024*1024) if elapsed > 0 else 0
                    total_size += fresh_msg.file.size
                    
                    await status_message.edit(
                        f"✅ **SENT:** `{file_name[:40]}...`\n"
                        f"⚡ Speed: `{speed:.1f} MB/s`\n"
                        f"📦 Files: {total_processed + 1}/{end_msg - start_msg + 1}",
                        buttons=get_progress_keyboard()
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
                        f"Waiting: `{e.seconds}s`\n"
                        f"Resume after cooldown...",
                        buttons=get_progress_keyboard()
                    )
                    await asyncio.sleep(e.seconds)
                
                except MemoryError:
                    logger.error("💥 RAM LIMIT HIT! Skipping file...")
                    await status_message.edit(
                        f"⚠️ **RAM Overflow!**\n"
                        f"File too large, skipping...\n"
                        f"File: `{file_name[:40]}...`",
                        buttons=get_progress_keyboard()
                    )
                    total_skipped += 1
                    retries = 0
                
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
                total_skipped += 1
                try: 
                    await bot_client.send_message(
                        event.chat_id, 
                        f"❌ **FAILED:** Message ID `{message.id}` after {MAX_RETRIES} attempts."
                    )
                except: 
                    pass
            
            total_processed += 1
            
            # Memory management: pause every 5 files
            if total_processed % 5 == 0:
                await asyncio.sleep(2)

        if is_running:
            overall_time = time.time() - overall_start
            avg_speed = total_size / overall_time / (1024*1024) if overall_time > 0 else 0
            
            await status_message.edit(
                f"🏁 **EXTREME MODE COMPLETE!**\n"
                f"✅ Files: `{total_processed}`\n"
                f"⏭️ Skipped: `{total_skipped}`\n"
                f"📦 Size: `{human_readable_size(total_size)}`\n"
                f"⚡ Avg Speed: `{avg_speed:.1f} MB/s`\n"
                f"⏱️ Time: `{time_formatter(overall_time)}`"
            )

    except Exception as e:
        await status_message.edit(f"💥 **Critical Error:** {str(e)[:100]}")
        logger.error(f"Transfer crashed: {e}")
    finally:
        is_running = False
        if session_id in active_sessions:
            del active_sessions[session_id]
