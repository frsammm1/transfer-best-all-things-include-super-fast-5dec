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
# Increased chunk size for speed, reduced queue size to maintain memory safety
CHUNK_SIZE = 4 * 1024 * 1024  # 4MB chunks (Better speed)
QUEUE_SIZE = 20  # 4MB * 20 = 80MB buffer (Same memory footprint as before, but less overhead)
UPLOAD_PART_SIZE = 16 * 1024 * 1024  # 16MB upload parts (Faster uploads)
UPDATE_INTERVAL = 5  # Progress update interval (seconds)
MAX_RETRIES = 3  # Retry attempts per file
FLOOD_SLEEP_THRESHOLD = 120
REQUEST_RETRIES = 10

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- RUNTIME STATE ---
active_sessions = {}
is_running = False
status_message = None
last_update_time = 0
current_task = None
stop_flag = False
