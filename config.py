import os
import logging

# --- TELEGRAM CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH")
# STRING_SESSION is no longer global, it's per user
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0)) # Owner ID
PORT = int(os.environ.get("PORT", 8080))

# --- OPTIMIZED SETTINGS FOR RENDER FREE TIER ---
# Reduced from 8MB to 1MB chunks (better for smoothness/speed on free tier)
CHUNK_SIZE = 1024 * 1024  # 1MB chunks
QUEUE_SIZE = 80  # 80MB buffer (1MB × 80) - Much safer for free tier
UPLOAD_PART_SIZE = 8192  # 8MB upload parts (was 32MB)
UPDATE_INTERVAL = 5  # Progress update interval (seconds)
MAX_RETRIES = 3  # Retry attempts per file (reduced from 4)
FLOOD_SLEEP_THRESHOLD = 120
REQUEST_RETRIES = 10  # Reduced from 20

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- RUNTIME STATE ---
# active_sessions stores metadata about the transfer (settings, steps, etc)
# It does NOT store the client anymore
active_sessions = {}
is_running = False
status_message = None
last_update_time = 0
current_task = None
stop_flag = False
