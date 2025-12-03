from telethon import Button

def get_settings_keyboard(session_id):
    """Main settings keyboard for file manipulation"""
    return [
        [
            Button.inline("📝 Filename: Find & Replace", f"set_fname_{session_id}"),
        ],
        [
            Button.inline("💬 Caption: Find & Replace", f"set_fcap_{session_id}"),
        ],
        [
            Button.inline("➕ Add Extra Caption", f"set_xcap_{session_id}"),
        ],
        [
            Button.inline("✅ Done - Start Transfer", f"confirm_{session_id}"),
            Button.inline("❌ Cancel", f"cancel_{session_id}")
        ]
    ]

def get_confirm_keyboard(session_id, settings):
    """Show current settings and confirm"""
    settings_text = "**Current Settings:**\n\n"
    
    if settings.get('find_name'):
        settings_text += f"📝 Filename:\n`{settings['find_name']}` → `{settings.get('replace_name', '')}`\n\n"
    
    if settings.get('find_cap'):
        settings_text += f"💬 Caption:\n`{settings['find_cap']}` → `{settings.get('replace_cap', '')}`\n\n"
    
    if settings.get('extra_cap'):
        settings_text += f"➕ Extra Caption:\n`{settings['extra_cap'][:50]}...`\n\n"
    
    if not any([settings.get('find_name'), settings.get('find_cap'), settings.get('extra_cap')]):
        settings_text += "⚠️ No modifications set\n\n"
    
    return settings_text, [
        [
            Button.inline("🔙 Back to Settings", f"back_{session_id}"),
            Button.inline("✅ Confirm & Start", f"start_{session_id}")
        ],
        [
            Button.inline("🗑️ Clear All Settings", f"clear_{session_id}"),
            Button.inline("❌ Cancel", f"cancel_{session_id}")
        ]
    ]

def get_skip_keyboard(session_id):
    """Skip option keyboard"""
    return [
        [Button.inline("⏭️ Skip", f"skip_{session_id}")],
        [Button.inline("❌ Cancel", f"cancel_{session_id}")]
    ]

def get_progress_keyboard():
    """Keyboard during transfer"""
    return [
        [Button.inline("🛑 Stop Transfer", "stop_transfer")]
    ]

def get_clone_info_keyboard():
    """Info keyboard for clone command"""
    return [
        [Button.inline("ℹ️ How to use?", "clone_help")],
        [Button.inline("📊 Bot Stats", "bot_stats")]
    ]
