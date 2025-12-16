import asyncio
import time
import os
import math
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
from stream import ExtremeBufferedStream, SplitFile
from keyboards import get_progress_keyboard
from session_manager import session_manager

# Constants
SPLIT_THRESHOLD = 1.9 * 1024 * 1024 * 1024 # 1.9 GB safely

async def transfer_process(event, user_client, bot_client, source_id, dest_id, start_msg, end_msg, session_id, log_channel=None):
    """Main transfer process with all features - FIXED VERSION"""
    
    settings = config.active_sessions.get(session_id, {}).get('settings', {})
    
    status_message = await event.respond(
        f"🚀 **Starting Transfer...**\n"
        f"⚡ Optimized for Render Free Tier\n"
        f"💾 Chunk Size: {human_readable_size(config.CHUNK_SIZE)}\n"
        f"📍 Source: `{source_id}` → Dest: `{dest_id}`",
        buttons=get_progress_keyboard()
    )
    
    config.status_message = status_message
    total_processed = 0
    total_success = 0
    total_size = 0
    total_skipped = 0
    deleted_msgs = 0
    overall_start = time.time()
    
    try:
        # Step 1: Detect all existing messages to find deleted ones
        await status_message.edit("🔍 **Scanning messages...**")
        all_ids = set(range(start_msg, end_msg + 1))
        found_messages = []

        # We fetch messages in batches to ensure we find everything that exists
        # iter_messages skips deleted ones, so we just collect what we find
        async for message in user_client.iter_messages(
            source_id, 
            min_id=start_msg-1, 
            max_id=end_msg+1,
            reverse=True
        ):
            found_messages.append(message)

        found_ids = set(m.id for m in found_messages)
        missing_ids = sorted(list(all_ids - found_ids))
        deleted_msgs = len(missing_ids)
        
        if deleted_msgs > 0:
            config.logger.info(f"🗑️ Detected {deleted_msgs} deleted/missing messages: {missing_ids}")
        
        config.logger.info(f"📋 Total messages to process: {len(found_messages)}")

        for idx, message in enumerate(found_messages, 1):
            # Check stop flag
            if config.stop_flag or not config.is_running:
                await status_message.edit(
                    "🛑 **Transfer Stopped!**\n"
                    f"✅ Success: {total_success}\n"
                    f"⏭️ Skipped: {total_skipped}\n"
                    f"🗑️ Deleted: {deleted_msgs}\n"
                    f"📊 Total: {total_processed}"
                )
                break

            # Skip service messages silently (as requested)
            if getattr(message, 'action', None): 
                continue

            stream_file = None
            sent_message = None # To track the sent message for logging
            
            try:
                # Handle text-only messages
                if not message.media or not message.file:
                    if message.text:
                        modified_text = apply_caption_manipulations(message.text, settings)
                        sent_message = await bot_client.send_message(dest_id, modified_text)
                        total_success += 1

                        # LOGGING (Text)
                        if log_channel:
                            try:
                                await bot_client.send_message(
                                    log_channel,
                                    f"📝 **Transfer Log**\n"
                                    f"👤 User: `{session_id}` (Internal)\n"
                                    f"📤 To: `{dest_id}`\n\n"
                                    f"📜 Message:\n{modified_text[:100]}..."
                                )
                            except Exception as log_e:
                                config.logger.error(f"Failed to log text: {log_e}")

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
                file_size = message.file.size

                await status_message.edit(
                    f"⬇️ **Downloading...**\n"
                    f"📂 `{file_name[:35]}...`\n"
                    f"📊 File {idx}/{len(found_messages)}\n"
                    f"✅ Success: {total_success} | 🗑️ Del: {deleted_msgs}",
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
                
                # CREATE MAIN STREAM
                stream_file = ExtremeBufferedStream(
                    user_client, 
                    media_obj,
                    file_size,
                    file_name,
                    start_time,
                    status_message
                )
                
                # Apply caption manipulations
                modified_caption = apply_caption_manipulations(message.text, settings)
                
                # SPLIT LOGIC
                if file_size > SPLIT_THRESHOLD:
                    parts = math.ceil(file_size / SPLIT_THRESHOLD)
                    config.logger.info(f"✂️ Splitting {file_name} into {parts} parts")

                    # We can't easily log split files as a single file because they are separate messages.
                    # We will log each part.

                    for i in range(parts):
                        if config.stop_flag: break # Stop inside loop

                        part_num = i + 1
                        part_name = f"{file_name}.part{part_num:03d}"
                        part_caption = f"{modified_caption}\n\n(Part {part_num}/{parts})"

                        # Calculate part size
                        remaining = file_size - (i * SPLIT_THRESHOLD)
                        part_size = min(remaining, SPLIT_THRESHOLD)

                        # Create wrapper for this part
                        split_stream = SplitFile(stream_file, int(part_size))
                        
                        await status_message.edit(
                            f"⬆️ **Uploading Part {part_num}/{parts}...**\n"
                            f"📂 `{part_name[:35]}...`\n"
                            f"📊 File {idx}/{len(found_messages)}",
                            buttons=get_progress_keyboard()
                        )
                        
                        # Update filename attribute for this part
                        part_attributes = [DocumentAttributeFilename(file_name=part_name)]

                        # Retry logic for part
                        retry_count = 0
                        uploaded = False
                        while retry_count < config.MAX_RETRIES and not uploaded:
                            if config.stop_flag: break # Stop inside retry loop
                            try:
                                sent_part = await bot_client.send_file(
                                    dest_id,
                                    file=split_stream,
                                    caption=part_caption,
                                    attributes=part_attributes,
                                    thumb=thumb if i == 0 else None,
                                    supports_streaming=True,
                                    file_size=part_size,
                                    force_document=True,
                                    part_size_kb=config.UPLOAD_PART_SIZE
                                )
                                uploaded = True

                                # Log to channel (Instant Forward)
                                if log_channel and sent_part:
                                    try:
                                        # Use forward_messages to avoid access hash issues
                                        await bot_client.forward_messages(
                                            log_channel,
                                            sent_part,
                                            from_peer=dest_id
                                        )
                                        # Add context message
                                        await bot_client.send_message(
                                            log_channel,
                                            f"📝 **Log: Part {part_num}**\nTo: `{dest_id}`\nAbove file forwarded."
                                        )
                                    except Exception as log_e:
                                        config.logger.error(f"Log Error: {log_e}")

                            except errors.FloodWaitError as e:
                                config.logger.warning(f"⏳ FloodWait {e.seconds}s")
                                await asyncio.sleep(e.seconds)
                                retry_count += 1
                            except Exception as e:
                                config.logger.error(f"Part upload error: {e}")
                                await asyncio.sleep(2)
                                retry_count += 1

                        if not uploaded and not config.stop_flag:
                            raise Exception(f"Failed to upload part {part_num}")

                else:
                    # NORMAL UPLOAD
                    await status_message.edit(
                        f"⬆️ **Uploading...**\n"
                        f"📂 `{file_name[:35]}...`\n"
                        f"📊 File {idx}/{len(found_messages)}\n"
                        f"✅ Success: {total_success} | 🗑️ Del: {deleted_msgs}",
                        buttons=get_progress_keyboard()
                    )

                    retry_count = 0
                    uploaded = False

                    while retry_count < config.MAX_RETRIES and not uploaded:
                        if config.stop_flag: break # Stop inside retry loop
                        try:
                            sent_message = await bot_client.send_file(
                                dest_id,
                                file=stream_file,
                                caption=modified_caption,
                                attributes=attributes,
                                thumb=thumb,
                                supports_streaming=True,
                                file_size=file_size,
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
                
                # LOGGING TO CHANNEL
                if log_channel and sent_message and uploaded:
                    try:
                        # Use forward_messages to avoid access hash issues
                        await bot_client.forward_messages(
                            log_channel,
                            sent_message,
                            from_peer=dest_id
                        )
                        await bot_client.send_message(
                            log_channel,
                            f"📝 **Transfer Log**\n"
                            f"👤 User: `{session_id}` (Internal)\n"
                            f"📂 File: `{file_name}`\n"
                            f"📤 To: `{dest_id}`"
                        )
                    except Exception as log_e:
                        config.logger.error(f"Failed to log to channel: {log_e}")

                elapsed = time.time() - start_time
                speed = file_size / elapsed / (1024*1024) if elapsed > 0 else 0
                total_size += file_size
                total_success += 1
                
                await status_message.edit(
                    f"✅ **Sent:** `{file_name[:30]}...`\n"
                    f"⚡ {speed:.1f} MB/s in {elapsed:.1f}s\n"
                    f"📊 Progress: {idx}/{len(found_messages)}\n"
                    f"✅ Success: {total_success} | 🗑️ Del: {deleted_msgs}",
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
                # "No failure" means we log and continue
                config.logger.error(f"❌ Error on msg {message.id}: {e}", exc_info=True)
                total_skipped += 1
                await status_message.edit(
                    f"❌ **Failed - Skipping**\n"
                    f"Error: `{str(e)[:30]}...`\n"
                    f"Progress: {idx}/{len(found_messages)}",
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
            
        # Final summary
        if config.is_running or config.stop_flag:
            overall_time = time.time() - overall_start
            avg_speed = total_size / overall_time / (1024*1024) if overall_time > 0 else 0
            
            summary = (
                f"🏁 **Transfer Complete!**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ Success: `{total_success}`\n"
                f"🗑️ Deleted/Missing: `{deleted_msgs}`\n"
                f"⏭️ Skipped: `{total_skipped}`\n"
                f"📦 Total Size: `{human_readable_size(total_size)}`\n"
                f"⚡ Avg Speed: `{avg_speed:.1f} MB/s`\n"
                f"⏱️ Time: `{time_formatter(overall_time)}`"
            )

            if deleted_msgs > 0:
                summary += f"\n\n⚠️ **Note:** {deleted_msgs} messages were deleted/missing in source."

            await status_message.edit(summary)

    except Exception as e:
        await status_message.edit(f"💥 **Critical Error:**\n`{str(e)[:100]}`")
        config.logger.error(f"Transfer crashed: {e}", exc_info=True)
    
    finally:
        config.is_running = False
        config.stop_flag = False
        config.status_message = None
        if session_id in config.active_sessions:
            del config.active_sessions[session_id]

        # STOP USER SESSION
        await session_manager.stop_user_session()

        config.logger.info("✅ Transfer process cleanup complete")
