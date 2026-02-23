# ii_config.py — safe defaults for local dev
import os, platform
from pathlib import Path

# --- App / server ---
APP_HOST = "127.0.0.1"
APP_PORT = 5051
DEBUG = True

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR   = str(BASE_DIR / "data")
MODELS_DIR = str(BASE_DIR / "models")
LOG_DIR    = str(BASE_DIR / "logs")
CACHE_DIR  = str(BASE_DIR / "cache")
TEST_MEDIA_DIR = str(BASE_DIR / "test_media")
for d in (DATA_DIR, MODELS_DIR, LOG_DIR, CACHE_DIR, TEST_MEDIA_DIR):
    os.makedirs(d, exist_ok=True)

LOG_FILE = str(Path(LOG_DIR) / "app.log")

# --- Vision / model ---
YOLO_WEIGHTS = str(Path(MODELS_DIR) / "hydration_model.pt")  # ok if missing
HSV_GREEN_THRESHOLD = 0.23
HYDRATION_NEED_BASELINE = 5

# --- Camera ---
USE_IP_CAMERA = False
CAMERA_URL = ""                 # e.g. "rtsp://user:pass@192.168.1.50:554/stream"
CAMERA_DEVICE_INDEX = 0         # your check showed device 0 works
CAPTURE_WIDTH  = 1280
CAPTURE_HEIGHT = 720
CAPTURE_FPS    = 15

# --- Hardware (ignored on Windows) ---
IS_PI = platform.machine().startswith("arm") or os.environ.get("IS_PI") == "1"
RELAY_PINS = [17]

# --- App features (stubs ok) ---
ZONE_SETTINGS = [{"id":1,"name":"Front Lawn"},{"id":2,"name":"Back Lawn"}]
LLM_MODEL = "local"
RAG_SERVER_URL = "http://127.0.0.1:8000"