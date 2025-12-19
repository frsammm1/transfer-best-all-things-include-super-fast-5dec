# 🚀 Extreme Transfer Bot v3.1 (Best UI/UX Update)

The ultimate high-performance Telegram File Transfer Bot, now with an enhanced sequential flow and complete **SaaS Platform** architecture.

## 🔥 New Features in v3.1

### 🌟 Improved Workflow (Best UI/UX)
- **Sequential Clone**: Simplified `/clone` command guides you step-by-step.
- **Range Selection**: Just send the first link and the last link. The bot automatically detects the channel/group.
- **Smart Link Detection**: Now supports Topic links (`t.me/c/ID/TOPIC/MSG`) correctly.
- **Auto-Detection**: Supports both Private (`t.me/c/..`) and Public (`t.me/username/..`) links.
- **Flexible Destination**: Choose "Transfer in Bot" or "Transfer to Channel".
- **Easy Input**: Forward a message from the destination channel to set it automatically.
- **Control**: New `/stop` and `/cancel` commands to manage tasks.

### 👑 Admin Panel
- **User Management**: Grant, revoke, and monitor user access.
- **Validity System**: Set expiration times for users (e.g., `1h`, `30d`).
- **Log Channel**: Configure a channel to receive logs of all user activities and transfers.
- **Commands**:
  - `/add_user ID DURATION` - Add/Renew user access (e.g., `/add_user 12345 30d`).
  - `/revoke ID` - Revoke user access immediately.
  - `/users` - List all active users and their expiration status.
  - `/set_log CHANNEL_ID` - Set the global log channel.

### 🔐 User Authentication
- **Secure Login**: Users log in with their own Telegram account via Phone + OTP (and 2FA if enabled).
- **Session Management**: Users can `/login` and `/logout`. Sessions are stored securely.
- **Privacy**: The bot uses the user's account *only* for transfers requested by them.

### 💳 Subscription System
- **Paid Access Only**: New users see a locked interface.
- **Request Access**: Users can send `/buy` to request a subscription from the admin.
- **Validity Tracking**: Automatic expiration of access.

### ⚡ Core Optimization
- **Sequential Processing**: Ensures stability and prevents 512MB RAM overload.
- **Dynamic Resource Locking**: Manages active sessions to prevent crashes.
- **Smart Split & Rename**: Handles 2GB+ files automatically.

---

## 🛠 Deployment

### Option 1: One-Click Heroku Deploy

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

1. Click the button above.
2. Fill in the required environment variables:
   - `API_ID`: Your Telegram API ID
   - `API_HASH`: Your Telegram API Hash
   - `BOT_TOKEN`: Your Bot Token
   - `ADMIN_ID`: Your Telegram User ID
3. Click "Deploy App".

### Option 2: Manual VPS/Local Deploy

1. Clone the repository.
   ```bash
   git clone https://github.com/yourusername/repo.git
   cd repo
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables (create a `.env` file or export them).

4. Run the bot:
   ```bash
   python3 main.py
   ```

---

## 🤖 Commands

### User
- `/start` - Check status and menu.
- `/login` - Login to your Telegram account.
- `/logout` - Logout.
- `/clone` - Start a new transfer task (Follow the interactive steps).
- `/stop` - Stop the current transfer immediately.
- `/cancel` - Cancel the current session setup.
- `/buy` - Request subscription extension.

### Admin
- `/add_user <id> <duration>`
- `/revoke <id>`
- `/users`
- `/set_log <channel_id>`
