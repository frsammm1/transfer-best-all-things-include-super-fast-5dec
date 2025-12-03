import os
import logging

# --- TELEGRAM CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH")
STRING_SESSION = os.environ.get("STRING_SESSION") 
BOT_TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 8080))

# --- EXTREME MODE SETTINGS ---
CHUNK_SIZE = 32 * 1024 * 1024  # 32MB chunks
QUEUE_SIZE = 5  # 160MB buffer (32MB × 5)
UPLOAD_PART_SIZE = 32768  # 32MB upload parts
UPDATE_INTERVAL = 10  # Progress update interval (seconds)
MAX_RETRIES = 4  # Retry attempts per file
FLOOD_SLEEP_THRESHOLD = 120
REQUEST_RETRIES = 20

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- RUNTIME STATE ---
pending_requests = {}
active_sessions = {}
is_running = False
status_message = None
last_update_time = 0
current_task = None
