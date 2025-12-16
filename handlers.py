import asyncio
import uuid
import time
import datetime
from telethon import events, Button, errors
from telethon.tl.types import User
import config
from keyboards import (
    get_settings_keyboard, get_confirm_keyboard,
    get_skip_keyboard, get_clone_info_keyboard,
    get_progress_keyboard
)
from transfer import transfer_process
import database as db
from session_manager import session_manager

# Login states
LOGIN_STATES = {} # user_id -> {'state': 'PHONE'|'CODE'|'PWD', 'phone': ...}

def register_handlers(bot_client):
    """Register all bot handlers"""
    
    # --- AUTH HELPERS ---
    async def get_user_status(user_id):
        if user_id == config.ADMIN_ID:
            return "ADMIN"
        is_valid, _, _ = await db.check_user(user_id)
        return "PAID" if is_valid else "FREE"

    # --- START HANDLER ---
    @bot_client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        user_id = event.sender_id
        status = await get_user_status(user_id)

        # Admin View
        if status == "ADMIN":
            await event.respond(
                "👑 **Admin Panel**\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Commands:\n"
                "`/add_user ID DURATION` (e.g., 1h, 30d)\n"
                "`/revoke ID`\n"
                "`/users` - List users\n"
                "`/set_log CHANNEL_ID`\n"
                "`/login` - Login to your account\n"
                "`/clone` - Start transfer"
            )
            raise events.StopPropagation

        # Paid User View
        if status == "PAID":
            is_valid, session, _ = await db.check_user(user_id)
            login_status = "✅ Logged In" if session else "❌ Not Logged In"

            await event.respond(
                f"🚀 **File Transfer Bot**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 Status: **Premium Member**\n"
                f"🔑 Session: **{login_status}**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"**Actions:**\n"
                f"1. `/login` - Connect Telegram Account\n"
                f"2. `/clone` - Start Transfer\n"
                f"3. `/buy` - Extend Validity\n"
                f"4. `/help` - Tutorial",
                buttons=get_clone_info_keyboard()
            )

        # Free/New User View
        else:
            await event.respond(
                "👋 **Welcome to Extreme Transfer Bot**\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "⚠️ **Access Restricted**\n"
                "You need to purchase a subscription to use this bot.\n\n"
                "**Features:**\n"
                "✅ Unlimited Transfers\n"
                "✅ 2GB+ File Support\n"
                "✅ Smart Split & Rename\n\n"
                "👉 Send `/buy` to request access."
            )
        raise events.StopPropagation

    # --- HELP HANDLER ---
    @bot_client.on(events.NewMessage(pattern='/help'))
    async def help_handler(event):
        await event.respond(
            "📚 **User Guide**\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "**1. Getting Started**\n"
            "• Send `/buy` to request access from the admin.\n"
            "• Wait for approval message.\n\n"

            "**2. Connecting Account (Important!)**\n"
            "• Send `/login`.\n"
            "• Enter your phone number (e.g., `+1234567890`).\n"
            "• Enter the code sent to your Telegram.\n"
            "⚠️ **Format:** You MUST enter the code as `1-2-3-4-5` (with dashes).\n"
            "• If you have 2FA, enter your password.\n\n"

            "**3. Cloning Files**\n"
            "• Use `/clone SOURCE_ID DEST_ID`.\n"
            "• Example: `/clone -100123456789 -100987654321`.\n"
            "• Configure settings (File Rename, Caption).\n"
            "• Send the range of message links (e.g., `https://t.me/c/../10 - https://t.me/c/../20`).\n\n"

            "**4. Stopping**\n"
            "• Click the `Stop Transfer` button during any operation.\n\n"

            "**Need Help?** Contact the admin."
        )
        raise events.StopPropagation

    # --- BUY HANDLER ---
    @bot_client.on(events.NewMessage(pattern='/buy'))
    async def buy_handler(event):
        user_id = event.sender_id
        user = await event.get_sender()
        username = f"@{user.username}" if user.username else f"User {user_id}"

        await event.respond(
            "⏳ **Request Sent!**\n\n"
            "The admin has been notified. You will receive a message once approved."
        )

        # Notify Admin
        try:
            await bot_client.send_message(
                config.ADMIN_ID,
                f"💸 **New Purchase Request**\n"
                f"User: {username} (`{user_id}`)\n"
                f"Action: Wants to buy/extend subscription.\n\n"
                f"Grant: `/add_user {user_id} 30d`"
            )
        except Exception as e:
            config.logger.error(f"Failed to notify admin: {e}")
        raise events.StopPropagation

    # --- ADMIN COMMANDS ---
    @bot_client.on(events.NewMessage(pattern=r'/add_user (\d+) (.+)'))
    async def add_user_handler(event):
        if event.sender_id != config.ADMIN_ID: return

        try:
            target_id = int(event.pattern_match.group(1))
            duration_str = event.pattern_match.group(2).lower()

            multiplier = 1
            if duration_str.endswith('m'): multiplier = 60
            elif duration_str.endswith('h'): multiplier = 3600
            elif duration_str.endswith('d'): multiplier = 86400

            duration = int(duration_str[:-1]) * multiplier

            new_expiry = await db.update_validity(target_id, duration)

            # Format to IST
            # IST is UTC+5:30. new_expiry is UNIX timestamp (UTC based).
            utc_dt = datetime.datetime.fromtimestamp(new_expiry, datetime.timezone.utc)
            ist_offset = datetime.timedelta(hours=5, minutes=30)
            ist_dt = utc_dt + ist_offset
            expiry_date = ist_dt.strftime('%Y-%m-%d %H:%M:%S')

            await event.respond(f"✅ User `{target_id}` updated!\nExpires: `{expiry_date}` (IST)")

            # Notify User
            try:
                await bot_client.send_message(
                    target_id,
                    f"🎉 **Subscription Activated!**\n\n"
                    f"You have been granted access until:\n`{expiry_date}` (IST)\n\n"
                    f"👉 Use `/login` to connect your account."
                )
            except:
                await event.respond(f"⚠️ Could not DM user `{target_id}`")

        except Exception as e:
            await event.respond(f"❌ Error: {e}")

    @bot_client.on(events.NewMessage(pattern=r'/revoke (\d+)'))
    async def revoke_user_handler(event):
        if event.sender_id != config.ADMIN_ID: return

        target_id = int(event.pattern_match.group(1))
        await db.revoke_user(target_id)
        await event.respond(f"🚫 User `{target_id}` revoked.")

    @bot_client.on(events.NewMessage(pattern='/users'))
    async def list_users_handler(event):
        if event.sender_id != config.ADMIN_ID: return

        users = await db.get_all_users()
        if not users:
            return await event.respond("No users found.")

        msg = "👥 **User List**\n━━━━━━━━━━━━━━━━\n"
        for uid, expiry, phone in users:
            remaining = int((expiry - time.time()) / 3600)
            status = f"{remaining}h left" if remaining > 0 else "EXPIRED"
            msg += f"🆔 `{uid}` | 📱 `{phone}` | ⏳ {status}\n"

        await event.respond(msg)

    @bot_client.on(events.NewMessage(pattern=r'/set_log (-?\d+)'))
    async def set_log_handler(event):
        if event.sender_id != config.ADMIN_ID: return

        log_id = event.pattern_match.group(1)
        await db.set_config("log_channel", log_id)
        await event.respond(f"✅ Log channel set to `{log_id}`")

    # --- LOGIN SYSTEM ---
    @bot_client.on(events.NewMessage(pattern='/login'))
    async def login_start(event):
        user_id = event.sender_id

        # Check validity (Admin always valid)
        if user_id != config.ADMIN_ID:
            is_valid, _, _ = await db.check_user(user_id)
            if not is_valid:
                return await event.respond("❌ **Subscription Required**\nUse `/buy` first.")

        # Check if already logged in
        is_valid, session, _ = await db.check_user(user_id)
        if session:
            return await event.respond(
                "✅ **Already Logged In!**\n"
                "Use `/logout` to change account."
            )

        LOGIN_STATES[user_id] = {'state': 'PHONE'}
        await event.respond(
            "🔐 **Login Step 1/3**\n\n"
            "Please send your **Phone Number** in international format.\n"
            "Example: `+1234567890`"
        )
        raise events.StopPropagation

    @bot_client.on(events.NewMessage())
    async def login_conversation(event):
        user_id = event.sender_id
        if user_id not in LOGIN_STATES:
            return # Not in login flow (allow other handlers to pick up)

        state_data = LOGIN_STATES[user_id]
        step = state_data['state']
        text = event.text.strip()

        try:
            if step == 'PHONE':
                await event.respond("⏳ **Sending Code...**\nPlease wait...")
                client = await session_manager.create_temp_client(user_id)

                try:
                    await client.send_code_request(text)
                    state_data['phone'] = text
                    state_data['state'] = 'CODE'
                    await event.respond(
                        "📩 **Login Step 2/3**\n\n"
                        "Enter the 5-digit code you received from Telegram.\n"
                        "⚠️ **IMPORTANT:** Use the format `1-2-3-4-5` (with dashes).\n"
                        "Do not send `12345`."
                    )
                except Exception as e:
                    await session_manager.remove_temp_client(user_id)
                    del LOGIN_STATES[user_id]
                    await event.respond(f"❌ Error: {e}\nTry `/login` again.")

            elif step == 'CODE':
                client = await session_manager.get_temp_client(user_id)
                if not client:
                    del LOGIN_STATES[user_id]
                    return await event.respond("❌ Session timed out. Use `/login` again.")

                phone = state_data['phone']

                # IMPORTANT: User requested NO STRIPPING of dashes.
                # If user sends "1-2-3-4-5", we send "1-2-3-4-5" to Telethon.
                code = text

                try:
                    await client.sign_in(phone, code)
                    # Login Success!
                    string_session = client.session.save()
                    await db.update_user_session(user_id, string_session, phone)

                    await session_manager.remove_temp_client(user_id)
                    del LOGIN_STATES[user_id]

                    await event.respond(
                        "✅ **Login Successful!**\n"
                        "You can now use `/clone` to transfer files."
                    )

                except errors.SessionPasswordNeededError:
                    state_data['state'] = 'PWD'
                    await event.respond(
                        "🔐 **Login Step 3/3**\n\n"
                        "Two-Step Verification is enabled.\n"
                        "Please enter your **Password**:"
                    )
                except Exception as e:
                    await event.respond(f"❌ Login Failed: {e}\nDid you use the `1-2-3-4-5` format?")

            elif step == 'PWD':
                client = await session_manager.get_temp_client(user_id)
                password = text

                try:
                    await client.sign_in(password=password)
                    string_session = client.session.save()
                    phone = state_data['phone']
                    await db.update_user_session(user_id, string_session, phone)

                    await session_manager.remove_temp_client(user_id)
                    del LOGIN_STATES[user_id]

                    await event.respond("✅ **Login Successful!**")
                except Exception as e:
                    await event.respond(f"❌ Password Error: {e}")

        except Exception as e:
            config.logger.error(f"Login Handler Error: {e}")
            await event.respond("❌ An error occurred.")
            if user_id in LOGIN_STATES:
                del LOGIN_STATES[user_id]
            await session_manager.remove_temp_client(user_id)

        # Stop propagation for login messages
        raise events.StopPropagation

    @bot_client.on(events.NewMessage(pattern='/logout'))
    async def logout_handler(event):
        user_id = event.sender_id
        await db.update_user_session(user_id, None, None)
        await event.respond("👋 **Logged Out**")
        raise events.StopPropagation

    # --- CLONE HANDLER (UPDATED) ---
    @bot_client.on(events.NewMessage(pattern='/clone'))
    async def clone_init(event):
        user_id = event.sender_id

        # 1. Check Validity
        if user_id != config.ADMIN_ID:
            is_valid, _, _ = await db.check_user(user_id)
            if not is_valid:
                await event.respond("❌ Subscription Expired/Missing. Use `/buy`.")
                raise events.StopPropagation

        # 2. Check Login
        is_valid, session, _ = await db.check_user(user_id)
        if not session:
            await event.respond("❌ Not Logged In. Use `/login` first.")
            raise events.StopPropagation

        # 3. Check if busy
        if config.is_running: 
            await event.respond(
                "⚠️ **Bot is Busy!**\n"
                "Someone is currently running a transfer.\n"
                "Please wait for them to finish."
            )
            raise events.StopPropagation
        
        try:
            args = event.text.split()
            if len(args) < 3:
                raise ValueError("Need source and destination IDs")
            
            source_id = int(args[1])
            dest_id = int(args[2])
            
            if source_id == dest_id:
                return await event.respond("❌ Source and destination cannot be same!")
            
            # Create session metadata
            session_id = str(uuid.uuid4())
            config.active_sessions[session_id] = {
                'source': source_id,
                'dest': dest_id,
                'settings': {},
                'chat_id': event.chat_id,
                'user_id': user_id, # Track who owns this session
                'step': 'settings'
            }
            
            await event.respond(
                f"✅ **Clone Setup**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📥 Source: `{source_id}`\n"
                f"📤 Destination: `{dest_id}`\n"
                f"━━━━━━━━━━━━━━━━━━━━\n",
                buttons=get_settings_keyboard(session_id)
            )
            
        except ValueError:
            await event.respond(
                "❌ **Invalid Format**\n\n"
                "`/clone SOURCE_ID DEST_ID`"
            )
        raise events.StopPropagation

    # --- START TRANSFER (UPDATED) ---
    # We need to catch the 'range' step from the message handler
    # So we need to update the generic message handler too.

    @bot_client.on(events.NewMessage())
    async def message_handler(event):
        # Ignore if in login flow
        if event.sender_id in LOGIN_STATES:
            return

        # Find active session
        session_id = None
        for sid, data in config.active_sessions.items():
            if data['chat_id'] == event.chat_id:
                session_id = sid
                break
        
        if not session_id:
            return
        
        session = config.active_sessions[session_id]
        step = session.get('step')
        user_id = event.sender_id
        
        if step == 'range':
            if "t.me" not in event.text:
                return await event.respond("❌ Invalid link format!")

            try:
                parts = event.text.strip().split("-")
                if len(parts) != 2:
                    raise ValueError("Need 2 links separated by -")

                msg1 = int(parts[0].strip().split("/")[-1])
                msg2 = int(parts[1].strip().split("/")[-1])

                if msg1 > msg2: msg1, msg2 = msg2, msg1

                # Check Login again before starting
                _, user_session, _ = await db.check_user(user_id)
                if not user_session:
                    return await event.respond("❌ Session lost. Login again.")

                # START TRANSFER
                # Start User Client dynamically
                try:
                    user_client = await session_manager.start_user_session(user_session, user_id)

                    # Only set running flag AFTER successfully getting the lock/session
                    config.is_running = True
                    config.stop_flag = False

                    # Get Log Channel
                    log_channel = await db.get_config("log_channel")

                    config.current_task = asyncio.create_task(
                        transfer_process(
                            event,
                            user_client,
                            bot_client,
                            session['source'],
                            session['dest'],
                            msg1,
                            msg2,
                            session_id,
                            log_channel=int(log_channel) if log_channel else None
                        )
                    )
                except Exception as e:
                    # Do not reset config.is_running here, as the error might be "Busy"
                    # If we set it to False, we might unlock a running process by mistake.
                    # We only set it to False if WE set it to True.
                    # But if start_user_session fails, we haven't set it True yet.
                    await event.respond(f"❌ Failed to start: {e}")

            except Exception as e:
                await event.respond(f"❌ Error: {e}")

        # --- SETTINGS HANDLERS (Same as before) ---
        elif step == 'fname_find':
            session['settings']['find_name'] = event.text.strip()
            session['step'] = 'fname_replace'
            await event.respond("Type REPLACEMENT text:", buttons=get_skip_keyboard(session_id))
        
        elif step == 'fname_replace':
            session['settings']['replace_name'] = event.text.strip()
            session['step'] = 'settings'
            await event.respond("✅ Filename rule set!", buttons=get_settings_keyboard(session_id))

        elif step == 'cap_find':
            session['settings']['find_cap'] = event.text.strip()
            session['step'] = 'cap_replace'
            await event.respond("Type REPLACEMENT text:", buttons=get_skip_keyboard(session_id))

        elif step == 'cap_replace':
            session['settings']['replace_cap'] = event.text.strip()
            session['step'] = 'settings'
            await event.respond("✅ Caption rule set!", buttons=get_settings_keyboard(session_id))

        elif step == 'extra_cap':
            session['settings']['extra_cap'] = event.text.strip()
            session['step'] = 'settings'
            await event.respond("✅ Extra caption set!", buttons=get_settings_keyboard(session_id))


    # --- CALLBACKS (Need to re-register these) ---
    @bot_client.on(events.CallbackQuery(pattern=r'set_fname_(.+)'))
    async def set_fname_cb(event):
        sid = event.data.decode().split('_')[2]
        if sid in config.active_sessions:
            config.active_sessions[sid]['step'] = 'fname_find'
            await event.edit("Type text to FIND in filename:", buttons=get_skip_keyboard(sid))

    @bot_client.on(events.CallbackQuery(pattern=r'set_fcap_(.+)'))
    async def set_fcap_cb(event):
        sid = event.data.decode().split('_')[2]
        if sid in config.active_sessions:
            config.active_sessions[sid]['step'] = 'cap_find'
            await event.edit("Type text to FIND in caption:", buttons=get_skip_keyboard(sid))

    @bot_client.on(events.CallbackQuery(pattern=r'set_xcap_(.+)'))
    async def set_xcap_cb(event):
        sid = event.data.decode().split('_')[2]
        if sid in config.active_sessions:
            config.active_sessions[sid]['step'] = 'extra_cap'
            await event.edit("Type text to ADD to caption:", buttons=get_skip_keyboard(sid))

    @bot_client.on(events.CallbackQuery(pattern=r'skip_(.+)'))
    async def skip_cb(event):
        sid = event.data.decode().split('_')[1]
        if sid in config.active_sessions:
            config.active_sessions[sid]['step'] = 'settings'
            await event.edit("✅ Settings:", buttons=get_settings_keyboard(sid))

    @bot_client.on(events.CallbackQuery(pattern=r'confirm_(.+)'))
    async def confirm_cb(event):
        sid = event.data.decode().split('_')[1]
        if sid in config.active_sessions:
            st, kb = get_confirm_keyboard(sid, config.active_sessions[sid]['settings'])
            await event.edit(st, buttons=kb)

    @bot_client.on(events.CallbackQuery(pattern=r'back_(.+)'))
    async def back_cb(event):
        sid = event.data.decode().split('_')[1]
        if sid in config.active_sessions:
            config.active_sessions[sid]['step'] = 'settings'
            await event.edit("✅ Settings:", buttons=get_settings_keyboard(sid))

    @bot_client.on(events.CallbackQuery(pattern=r'clear_(.+)'))
    async def clear_cb(event):
        sid = event.data.decode().split('_')[1]
        if sid in config.active_sessions:
            config.active_sessions[sid]['settings'] = {}
            config.active_sessions[sid]['step'] = 'settings'
            await event.edit("🗑️ Settings Cleared", buttons=get_settings_keyboard(sid))

    @bot_client.on(events.CallbackQuery(pattern=r'start_(.+)'))
    async def start_cb(event):
        sid = event.data.decode().split('_')[1]
        if sid in config.active_sessions:
            config.active_sessions[sid]['step'] = 'range'
            await event.edit(
                "📍 **Send Message Range**\n"
                "Send: `link1 - link2`\n"
                "Example: `https://t.me/c/xx/10 - https://t.me/c/xx/20`"
            )

    @bot_client.on(events.CallbackQuery(pattern=r'cancel_(.+)'))
    async def cancel_cb(event):
        sid = event.data.decode().split('_')[1]
        if sid in config.active_sessions:
            del config.active_sessions[sid]
        await event.edit("❌ Cancelled")

    @bot_client.on(events.CallbackQuery(pattern=b'stop_transfer'))
    async def stop_cb(event):
        if config.is_running:
            config.stop_flag = True
            await event.answer("🛑 Stopping...", alert=True)

    @bot_client.on(events.CallbackQuery(pattern=b'clone_help'))
    async def help_cb(event):
        await event.answer("Check /help for details", alert=True)

    @bot_client.on(events.CallbackQuery(pattern=b'bot_stats'))
    async def stats_cb(event):
        await event.answer("Running in Extreme Mode", alert=True)

    config.logger.info("✅ Handlers Registered")
