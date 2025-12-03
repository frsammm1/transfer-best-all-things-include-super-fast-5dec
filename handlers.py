import asyncio
import uuid
from telethon import events
import config
from keyboards import (
    get_settings_keyboard, get_confirm_keyboard,
    get_skip_keyboard, get_clone_info_keyboard
)
from transfer import transfer_process

def register_handlers(user_client, bot_client):
    """Register all bot handlers"""
    
    @bot_client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        await event.respond(
            "🚀 **EXTREME MODE BOT v2.0**\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ Chunks: **{config.CHUNK_SIZE // (1024*1024)}MB** × {config.QUEUE_SIZE} Queue\n"
            f"💾 Buffer: **{(config.CHUNK_SIZE * config.QUEUE_SIZE) // (1024*1024)}MB**\n"
            f"🔥 Upload Parts: **{config.UPLOAD_PART_SIZE // 1024}MB**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "**Features:**\n"
            "✅ All file types support\n"
            "✅ Video → MP4 conversion\n"
            "✅ Smart format detection\n"
            "✅ Filename manipulation\n"
            "✅ Caption manipulation\n"
            "✅ Extra caption support\n\n"
            "**Commands:**\n"
            "`/clone` - Start cloning\n"
            "`/stats` - Bot statistics\n"
            "`/help` - Detailed guide\n\n"
            "⚠️ **Warning:** High RAM usage!",
            buttons=get_clone_info_keyboard()
        )
    
    @bot_client.on(events.NewMessage(pattern='/help'))
    async def help_handler(event):
        await event.respond(
            "📚 **EXTREME MODE - User Guide**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "**Step 1:** Use `/clone` command\n"
            "Format: `/clone SOURCE_ID DEST_ID`\n"
            "Example: `/clone -1001234567 -1009876543`\n\n"
            "**Step 2:** Configure Settings\n"
            "• Filename Find & Replace\n"
            "• Caption Find & Replace\n"
            "• Add Extra Caption\n"
            "• Or skip all (direct transfer)\n\n"
            "**Step 3:** Provide Message Range\n"
            "Send two Telegram message links:\n"
            "`https://t.me/c/xxx/10 - https://t.me/c/xxx/20`\n\n"
            "**Supported Files:**\n"
            "• Videos (auto MP4 conversion)\n"
            "• Images (auto JPG conversion)\n"
            "• Documents (PDF, TXT, HTML, etc.)\n"
            "• Text messages\n"
            "• All Telegram media types\n\n"
            "**Tips:**\n"
            "• Use channel/group IDs (start with -100)\n"
            "• Ensure bot is admin in destination\n"
            "• Monitor RAM during large transfers\n"
            "• Use `/stop` to halt mid-transfer"
        )
    
    @bot_client.on(events.NewMessage(pattern='/clone'))
    async def clone_init(event):
        if config.is_running: 
            return await event.respond(
                "⚠️ **Already running a task!**\n"
                "Use `/stop` to cancel current transfer."
            )
        try:
            args = event.text.split()
            if len(args) < 3:
                raise ValueError("Invalid arguments")
            
            source_id = int(args[1])
            dest_id = int(args[2])
            
            # Create session
            session_id = str(uuid.uuid4())
            config.active_sessions[session_id] = {
                'source': source_id,
                'dest': dest_id,
                'settings': {},
                'chat_id': event.chat_id,
                'step': 'settings'
            }
            
            await event.respond(
                f"✅ **Clone Configuration Started**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📥 Source: `{source_id}`\n"
                f"📤 Destination: `{dest_id}`\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"**Configure your transfer settings:**\n"
                f"(All settings are optional)\n\n"
                f"Session ID: `{session_id[:8]}...`",
                buttons=get_settings_keyboard(session_id)
            )
            
        except Exception as e:
            await event.respond(
                "❌ **Invalid Command Format**\n\n"
                "**Usage:**\n"
                "`/clone SOURCE_ID DEST_ID`\n\n"
                "**Example:**\n"
                "`/clone -1001234567890 -1009876543210`\n\n"
                "💡 Get IDs using @userinfobot"
            )
    
    @bot_client.on(events.CallbackQuery(pattern=b'clone_help'))
    async def clone_help_callback(event):
        await event.answer()
        await event.respond(
            "📖 **How to Use Clone Command**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "1️⃣ Get Source & Destination IDs\n"
            "   Use @userinfobot or @getidsbot\n\n"
            "2️⃣ Run command:\n"
            "   `/clone -1001234 -1009876`\n\n"
            "3️⃣ Configure settings (optional)\n"
            "   • Filename modifications\n"
            "   • Caption modifications\n"
            "   • Extra captions\n\n"
            "4️⃣ Send message range\n"
            "   Two Telegram links separated by '-'\n\n"
            "✅ Transfer starts automatically!"
        )
    
    @bot_client.on(events.CallbackQuery(pattern=b'bot_stats'))
    async def stats_callback(event):
        await event.answer()
        await event.respond(
            f"📊 **EXTREME MODE Statistics**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ Chunk Size: **{config.CHUNK_SIZE // (1024*1024)}MB**\n"
            f"💾 Queue Size: **{config.QUEUE_SIZE} chunks**\n"
            f"📦 Buffer: **{(config.CHUNK_SIZE * config.QUEUE_SIZE) // (1024*1024)}MB**\n"
            f"📤 Upload Parts: **{config.UPLOAD_PART_SIZE // 1024}MB**\n"
            f"🔄 Max Retries: **{config.MAX_RETRIES}**\n"
            f"⏱️ Update Interval: **{config.UPDATE_INTERVAL}s**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🚀 Status: **{'🟢 Running' if config.is_running else '🔴 Idle'}**\n"
            f"📊 Active Sessions: **{len(config.active_sessions)}**"
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'set_fname_(.+)'))
    async def set_filename_callback(event):
        session_id = event.data.decode().split('_')[2]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['step'] = 'fname_find'
        await event.edit(
            "📝 **Filename Modification**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Enter text to **FIND** in filenames:\n"
            "(Send text or use Skip button)\n\n"
            "Example: `S01E` or `720p`",
            buttons=get_skip_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'set_fcap_(.+)'))
    async def set_caption_find_callback(event):
        session_id = event.data.decode().split('_')[2]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['step'] = 'cap_find'
        await event.edit(
            "💬 **Caption Modification**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Enter text to **FIND** in captions:\n"
            "(Send text or use Skip button)\n\n"
            "Example: `@OldChannel` or `Old Text`",
            buttons=get_skip_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'set_xcap_(.+)'))
    async def set_extra_caption_callback(event):
        session_id = event.data.decode().split('_')[2]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['step'] = 'extra_cap'
        await event.edit(
            "➕ **Extra Caption**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Enter text to **ADD** at end of captions:\n"
            "(Send text or use Skip button)\n\n"
            "Example: `@MyChannel` or `Join us!`",
            buttons=get_skip_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'skip_(.+)'))
    async def skip_callback(event):
        session_id = event.data.decode().split('_')[1]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        step = config.active_sessions[session_id]['step']
        
        # Skip current step
        if step == 'fname_find':
            config.active_sessions[session_id]['step'] = 'settings'
        elif step == 'cap_find':
            config.active_sessions[session_id]['step'] = 'settings'
        elif step == 'extra_cap':
            config.active_sessions[session_id]['step'] = 'settings'
        
        await event.answer("⏭️ Skipped!", alert=False)
        await event.edit(
            f"✅ **Settings Menu**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Configure your transfer:",
            buttons=get_settings_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'confirm_(.+)'))
    async def confirm_callback(event):
        session_id = event.data.decode().split('_')[1]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        settings = config.active_sessions[session_id]['settings']
        settings_text, keyboard = get_confirm_keyboard(session_id, settings)
        
        await event.edit(
            f"🔍 **Review Settings**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{settings_text}"
            f"Ready to proceed?",
            buttons=keyboard
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'back_(.+)'))
    async def back_callback(event):
        session_id = event.data.decode().split('_')[1]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        await event.edit(
            "✅ **Settings Menu**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Configure your transfer:",
            buttons=get_settings_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'clear_(.+)'))
    async def clear_callback(event):
        session_id = event.data.decode().split('_')[1]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['settings'] = {}
        await event.answer("🗑️ All settings cleared!", alert=True)
        await event.edit(
            "✅ **Settings Cleared**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Configure your transfer:",
            buttons=get_settings_keyboard(session_id)
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'start_(.+)'))
    async def start_transfer_callback(event):
        session_id = event.data.decode().split('_')[1]
        if session_id not in config.active_sessions:
            return await event.answer("❌ Session expired!", alert=True)
        
        config.active_sessions[session_id]['step'] = 'range'
        await event.edit(
            "📍 **Send Message Range**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Send two Telegram message links:\n"
            "`https://t.me/c/xxx/10 - https://t.me/c/xxx/20`\n\n"
            "**Format:**\n"
            "• Links separated by '-'\n"
            "• Must be from source channel\n"
            "• Range: Start to End\n\n"
            "💡 Open source channel, copy message links"
        )
    
    @bot_client.on(events.CallbackQuery(pattern=r'cancel_(.+)'))
    async def cancel_callback(event):
        session_id = event.data.decode().split('_')[1]
        if session_id in config.active_sessions:
            del config.active_sessions[session_id]
        await event.answer("❌ Cancelled!", alert=True)
        await event.edit("❌ **Transfer Cancelled**")
    
    @bot_client.on(events.CallbackQuery(pattern=b'stop_transfer'))
    async def stop_transfer_callback(event):
        config.is_running = False
        if config.current_task:
            config.current_task.cancel()
        await event.answer("🛑 Stopping transfer...", alert=True)
    
    @bot_client.on(events.NewMessage())
    async def message_handler(event):
        
        # Find active session for this chat
        session_id = None
        for sid, data in config.active_sessions.items():
            if data['chat_id'] == event.chat_id:
                session_id = sid
                break
        
        if not session_id:
            return
        
        session = config.active_sessions[session_id]
        step = session.get('step')
        
        # Handle different steps
        if step == 'fname_find':
            session['settings']['find_name'] = event.text
            session['step'] = 'fname_replace'
            await event.respond(
                "✅ **Find text saved!**\n\n"
                "Now enter text to **REPLACE** with:\n"
                "(Send text or use Skip button)",
                buttons=get_skip_keyboard(session_id)
            )
        
        elif step == 'fname_replace':
            session['settings']['replace_name'] = event.text
            session['step'] = 'settings'
            await event.respond(
                "✅ **Filename modification set!**\n\n"
                f"Find: `{session['settings']['find_name']}`\n"
                f"Replace: `{event.text}`",
                buttons=get_settings_keyboard(session_id)
            )
        
        elif step == 'cap_find':
            session['settings']['find_cap'] = event.text
            session['step'] = 'cap_replace'
            await event.respond(
                "✅ **Find text saved!**\n\n"
                "Now enter text to **REPLACE** with:\n"
                "(Send text or use Skip button)",
                buttons=get_skip_keyboard(session_id)
            )
        
        elif step == 'cap_replace':
            session['settings']['replace_cap'] = event.text
            session['step'] = 'settings'
            await event.respond(
                "✅ **Caption modification set!**\n\n"
                f"Find: `{session['settings']['find_cap']}`\n"
                f"Replace: `{event.text}`",
                buttons=get_settings_keyboard(session_id)
            )
        
        elif step == 'extra_cap':
            session['settings']['extra_cap'] = event.text
            session['step'] = 'settings'
            await event.respond(
                "✅ **Extra caption set!**\n\n"
                f"Caption: `{event.text[:100]}...`",
                buttons=get_settings_keyboard(session_id)
            )
        
        elif step == 'range' and "t.me" in event.text:
            try:
                links = event.text.strip().split("-")
                msg1 = int(links[0].strip().split("/")[-1])
                msg2 = int(links[1].strip().split("/")[-1])
                if msg1 > msg2: 
                    msg1, msg2 = msg2, msg1
                
                config.is_running = True
                config.current_task = asyncio.create_task(
                    transfer_process(
                        event, 
                        user_client,
                        bot_client,
                        session['source'], 
                        session['dest'], 
                        msg1, 
                        msg2,
                        session_id
                    )
                )
            except Exception as e: 
                await event.respond(
                    f"❌ **Invalid Range Format**\n\n"
                    f"Error: `{str(e)}`\n\n"
                    f"Expected format:\n"
                    f"`https://t.me/c/xxx/10 - https://t.me/c/xxx/20`"
                )
    
    @bot_client.on(events.NewMessage(pattern='/stats'))
    async def stats_handler(event):
        await event.respond(
            f"📊 **EXTREME MODE Stats**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ Chunk: **{config.CHUNK_SIZE // (1024*1024)}MB**\n"
            f"💾 Buffer: **{(config.CHUNK_SIZE * config.QUEUE_SIZE) // (1024*1024)}MB**\n"
            f"📤 Upload: **{config.UPLOAD_PART_SIZE // 1024}MB parts**\n"
            f"🔄 Retries: **{config.MAX_RETRIES}**\n"
            f"⏱️ Updates: **Every {config.UPDATE_INTERVAL}s**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🚀 Status: **{'Running' if config.is_running else 'Idle'}**\n"
            f"📊 Sessions: **{len(config.active_sessions)}**"
        )
    
    @bot_client.on(events.NewMessage(pattern='/stop'))
    async def stop_handler(event):
        if not config.is_running:
            return await event.respond("⚠️ No active transfer to stop!")
        
        config.is_running = False
        if config.current_task: 
            config.current_task.cancel()
        await event.respond("🛑 **Transfer stopped!**")
    
    config.logger.info("✅ All handlers registered successfully!")
