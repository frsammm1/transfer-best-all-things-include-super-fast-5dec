import asyncio
import time
import os
from telethon import errors
from telethon.tl.types import (
    DocumentAttributeFilename, 
    DocumentAttributeVideo, 
    DocumentAttributeAudio
)
import config
from utils import (
    human_readable_size, time_formatter, 
    get_target_info, apply_filename_manipulations,
    apply_caption_manipulations, sanitize_filename
)
from stream import ExtremeBufferedStream
from keyboards import get_progress_keyboard

async def transfer_process(event, user_client, bot_client, source_id, dest_id, start_msg, end_msg, session_id):
    """Main transfer process with all features - FIXED VERSION"""
    
    settings = config.active_sessions.get(session_id, {}).get('settings', {})
    
    status_message = await event.respond(
        f"🚀 **Starting Transfer...**\n"
        f"⚡ Optimized for Render Free Tier\n"
        f"💾 Buffer: 16MB (8MB × 2)\n"
        f"📍 Source: `{source_id}` → Dest: `{dest_id}`",
        buttons=get_progress_keyboard()
    )
    
    config.status_message = status_message
    total_processed = 0
    total_success = 0
    total_size = 0
    total_skipped = 0
    overall_start = time.time()
    
    try:
        messages = []
        async for message in user_client.iter_messages(
            source_id, 
            min_id=start_msg-1, 
            max_id=end_msg+1, 
            reverse=True
        ):
            messages.append(message)
        
        config.logger.info(f"📋 Total messages to process: {len(messages)}")
        
        for idx, message in enumerate(messages, 1):
            # Check stop flag
            if config.stop_flag or not config.is_running:
                await status_message.edit(
                    "🛑 **Transfer Stopped!**\n"
                    f"✅ Success: {total_success}\n"
                    f"⏭️ Skipped: {total_skipped}\n"
                    f"📊 Total: {total_processed}"
                )
                break

            # Skip service messages
            if getattr(message, 'action', None): 
                continue

            stream_file = None
            
            try:
                # Handle text-only messages
                if not message.media or not message.file:
                    if message.text:
                        modified_text = apply_caption_manipulations(message.text, settings)
                        await bot_client.send_message(dest_id, modified_text)
                        total_success += 1
                    total_processed += 1
                    continue

                # Get file info
                file_name, mime_type, is_video_mode = get_target_info(message)
                
                if not file_name:
                    total_processed += 1
                    continue
                
                # Apply manipulations
                file_name = apply_filename_manipulations(file_name, settings)
                file_name = sanitize_filename(file_name)

                await status_message.edit(
                    f"⬇️ **Downloading...**\n"
                    f"📂 `{file_name[:35]}...`\n"
                    f"📊 File {idx}/{len(messages)}\n"
                    f"✅ Success: {total_success} | ⏭️ Skip: {total_skipped}",
                    buttons=get_progress_keyboard()
                )

                start_time = time.time()
                
                # Prepare attributes
                attributes = [DocumentAttributeFilename(file_name=file_name)]
                
                if hasattr(message, 'document') and message.document:
                    for attr in message.document.attributes:
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
                    thumb = await user_client.download_media(message, thumb=-1)
                except:
                    pass
                
                # Prepare media object
                media_obj = (message.media.document 
                            if hasattr(message.media, 'document') 
                            else message.media.photo)
                
                # CREATE STREAM
                stream_file = ExtremeBufferedStream(
                    user_client, 
                    media_obj,
                    message.file.size,
                    file_name,
                    start_time,
                    status_message
                )
                
                # Apply caption manipulations
                modified_caption = apply_caption_manipulations(message.text, settings)
                
                # Update status before upload
                await status_message.edit(
                    f"⬆️ **Uploading...**\n"
                    f"📂 `{file_name[:35]}...`\n"
                    f"📊 File {idx}/{len(messages)}\n"
                    f"✅ Success: {total_success} | ⏭️ Skip: {total_skipped}",
                    buttons=get_progress_keyboard()
                )
                
                # UPLOAD WITH RETRY LOGIC
                retry_count = 0
                uploaded = False
                
                while retry_count < config.MAX_RETRIES and not uploaded:
                    try:
                        await bot_client.send_file(
                            dest_id,
                            file=stream_file,
                            caption=modified_caption,
                            attributes=attributes,
                            thumb=thumb,
                            supports_streaming=True,
                            file_size=message.file.size,
                            force_document=not is_video_mode,
                            part_size_kb=config.UPLOAD_PART_SIZE
                        )
                        uploaded = True
                        
                    except errors.FloodWaitError as e:
                        config.logger.warning(f"⏳ FloodWait {e.seconds}s")
                        await status_message.edit(
                            f"⏳ **Cooling Down...**\n"
                            f"Waiting: `{e.seconds}s`\n"
                            f"Then resuming...",
                            buttons=get_progress_keyboard()
                        )
                        await asyncio.sleep(e.seconds)
                        retry_count += 1
                        
                    except Exception as e:
                        config.logger.error(f"Upload error: {e}")
                        retry_count += 1
                        if retry_count < config.MAX_RETRIES:
                            await asyncio.sleep(2)
                        else:
                            raise
                
                # Cleanup thumbnail
                if thumb and os.path.exists(thumb): 
                    try:
                        os.remove(thumb)
                    except:
                        pass
                
                elapsed = time.time() - start_time
                speed = message.file.size / elapsed / (1024*1024) if elapsed > 0 else 0
                total_size += message.file.size
                total_success += 1
                
                await status_message.edit(
                    f"✅ **Sent:** `{file_name[:30]}...`\n"
                    f"⚡ {speed:.1f} MB/s in {elapsed:.1f}s\n"
                    f"📊 Progress: {idx}/{len(messages)}\n"
                    f"✅ Success: {total_success} | ⏭️ Skip: {total_skipped}",
                    buttons=get_progress_keyboard()
                )

            except MemoryError:
                config.logger.error("💥 RAM LIMIT! Skipping file...")
                await status_message.edit(
                    f"⚠️ **RAM Overflow - Skipped!**\n"
                    f"File: `{file_name[:30] if 'file_name' in locals() else 'Unknown'}...`\n"
                    f"Continuing with next...",
                    buttons=get_progress_keyboard()
                )
                total_skipped += 1
                await asyncio.sleep(2)
            
            except Exception as e:
                config.logger.error(f"❌ Error on msg {message.id}: {e}")
                total_skipped += 1
                await status_message.edit(
                    f"❌ **Failed - Skipping**\n"
                    f"Error: `{str(e)[:30]}...`\n"
                    f"Progress: {idx}/{len(messages)}",
                    buttons=get_progress_keyboard()
                )
                await asyncio.sleep(1)
            
            finally:
                # CRITICAL: Always close stream
                if stream_file:
                    try:
                        await stream_file.close()
                    except:
                        pass
            
            total_processed += 1
            
            # Memory management: Small pause every 3 files
            if total_processed % 3 == 0:
                await asyncio.sleep(1)

        # Final summary
        if config.is_running or config.stop_flag:
            overall_time = time.time() - overall_start
            avg_speed = total_size / overall_time / (1024*1024) if overall_time > 0 else 0
            
            await status_message.edit(
                f"🏁 **Transfer Complete!**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ Success: `{total_success}`\n"
                f"⏭️ Skipped: `{total_skipped}`\n"
                f"📦 Total Size: `{human_readable_size(total_size)}`\n"
                f"⚡ Avg Speed: `{avg_speed:.1f} MB/s`\n"
                f"⏱️ Time: `{time_formatter(overall_time)}`"
            )

    except Exception as e:
        await status_message.edit(f"💥 **Critical Error:**\n`{str(e)[:100]}`")
        config.logger.error(f"Transfer crashed: {e}", exc_info=True)
    
    finally:
        config.is_running = False
        config.stop_flag = False
        config.status_message = None
        if session_id in config.active_sessions:
            del config.active_sessions[session_id]
        config.logger.info("✅ Transfer process cleanup complete")
