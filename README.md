# 🚀 Extreme Transfer Bot v3.0

**A High-Performance Telegram File Transfer Bot with Admin Panel & User System.**

Designed for **Render Free Tier (512MB RAM)** with strict resource management.

---

## 🔥 Features

*   **⚡ Extreme Speed:** Optimized `uvloop` & `asyncio` for maximum throughput.
*   **👥 Multi-User System:** Sell access to other users with validity periods (e.g., 30 days).
*   **👑 Admin Panel:** Manage users, revoke access, and monitor logs.
*   **🔐 Secure Login:** Users login via Phone Number + OTP (no API ID/Hash needed for them).
*   **📝 Log Channel:** Auto-logs transferred files to your channel (Zero Bandwidth Cost).
*   **🛡️ RAM Optimized:** Global Queue system ensures only **one** transfer runs at a time to prevent crashes.
*   **✂️ Smart Splitting:** Automatically splits files > 1.9GB.
*   **✏️ Manipulation:** Rename files, replace captions, and add custom text.

---

## 🛠️ Deployment

### 1. Variables
Set these Environment Variables in your deployment (Render/Heroku/VPS):

| Variable | Description |
| :--- | :--- |
| `API_ID` | Your App API ID (from my.telegram.org) |
| `API_HASH` | Your App API Hash |
| `BOT_TOKEN` | Bot Token from @BotFather |
| `ADMIN_ID` | **Your Telegram User ID** (to access Admin Panel) |

### 2. Deploy on Render
1.  Fork this repo.
2.  Create a **Web Service** on Render.
3.  Connect your repo.
4.  Runtime: **Python 3**.
5.  Build Command: `pip install -r requirements.txt`
6.  Start Command: `python3 main.py`
7.  Add the **Environment Variables**.

---

## 🤖 Commands

### 👑 Admin Commands (You Only)
*   `/add_user <id> <duration>` - Grant access (e.g., `/add_user 123456789 30d`)
    *   Durations: `m` (minutes), `h` (hours), `d` (days)
*   `/revoke <id>` - Revoke user access immediately.
*   `/users` - List all active subscribers.
*   `/set_log <channel_id>` - Set the channel for file logs.

### 👤 User Commands
*   `/start` - Check status.
*   `/login` - Login with Phone Number.
*   `/logout` - Disconnect session.
*   `/buy` - Request subscription from Admin.
*   `/clone <source> <dest>` - Start Transfer.
*   `/help` - Usage guide.

---

## ⚠️ Important Notes

1.  **Global Queue:** Only **one person** can transfer at a time. If someone else is transferring, others must wait. This is to protect the server from crashing (512MB RAM limit).
2.  **Database:** On Render Free Tier, the database (user list) **resets** every time the bot redeploys/restarts.
3.  **Privacy:** User session strings are stored locally in `bot_data.db`.

---

## 📝 How to Transfer (User Guide)

1.  **Login:** Send `/login` and follow instructions.
2.  **Setup:** Send `/clone source_id dest_id`.
    *   Example: `/clone -100123456 -100987654`
3.  **Configure:** Use buttons to rename files or change captions (optional).
4.  **Send Range:** Send the link of the first and last message.
    *   Example: `https://t.me/c/xxx/10 - https://t.me/c/xxx/20`
5.  **Relax:** The bot will transfer everything sequentially.

---

**Version:** 3.0 | **License:** MIT
