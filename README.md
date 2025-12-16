# 🚀 Extreme Transfer Bot v3.1 (Best UI/UX Update)

The ultimate high-performance Telegram File Transfer Bot, now with an enhanced sequential flow and complete **SaaS Platform** architecture.

## 🔥 New Features in v3.1

### 🌟 Improved Workflow (Best UI/UX)
- **Sequential Clone**: Simplified `/clone` command guides you step-by-step.
- **Range Selection**: Just send the first link and the last link. The bot automatically detects the channel/group.
- **Auto-Detection**: Supports both Private (`t.me/c/..`) and Public (`t.me/username/..`) links.
- **Destination Prompt**: Asks for destination ID clearly after range selection.

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

### 1. Variables
| Variable | Description |
| :--- | :--- |
| `API_ID` | Your Telegram API ID |
| `API_HASH` | Your Telegram API Hash |
| `BOT_TOKEN` | Bot Token from @BotFather |
| `ADMIN_ID` | Your Telegram User ID (Controller) |
| `PORT` | Web server port (Default: 8080) |

### 2. Deploy
1. Clone the repository.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run: `python3 main.py`.

---

## 🤖 Commands

### User
- `/start` - Check status and menu.
- `/login` - Login to your Telegram account.
- `/logout` - Logout.
- `/clone` - Start a new transfer task (Follow the interactive steps).
- `/buy` - Request subscription extension.

### Admin
- `/add_user <id> <duration>`
- `/revoke <id>`
- `/users`
- `/set_log <channel_id>`
