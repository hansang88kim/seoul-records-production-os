"""
Seoul Records Production OS — App Configuration
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"
PRESETS_DIR = BASE_DIR / "presets"
TEMPLATES_DIR = BASE_DIR / "templates"

# ─── Provider Selection ───────────────────────────────────────────────────────
COMPOSER_PROVIDER = os.getenv("COMPOSER_PROVIDER", "mock")
SUNO_DOWNLOAD_FORMAT = os.getenv("SUNO_DOWNLOAD_FORMAT", "wav")
ALLOW_MP3_FOR_DISTRIBUTION = os.getenv("ALLOW_MP3_FOR_DISTRIBUTION", "false").lower() == "true"
ALLOW_THIRD_PARTY_SUNO = os.getenv("ALLOW_THIRD_PARTY_SUNO", "false").lower() == "true"

# ─── Suno Settings ────────────────────────────────────────────────────────────
SUNO_LOCAL_API_BASE_URL = os.getenv("SUNO_LOCAL_API_BASE_URL", "http://localhost:3000")
MAX_CONCURRENT_SUNO_JOBS = 1

# ─── Auto Mode Timing ─────────────────────────────────────────────────────────
AUTO_MODE_INTERVAL_SECONDS = int(os.getenv("AUTO_MODE_INTERVAL_SECONDS", "300"))
AUTO_MODE_TEST_INTERVAL_SECONDS = int(os.getenv("AUTO_MODE_TEST_INTERVAL_SECONDS", "10"))

# ─── Target Duration ──────────────────────────────────────────────────────────
TARGET_DURATION_MIN_SECONDS = 210  # 3:30
TARGET_DURATION_MAX_SECONDS = 240  # 4:00

# ─── Track Count Options ──────────────────────────────────────────────────────
TRACK_COUNT_OPTIONS = [1, 5, 10, 15, 20]

# ─── Models ───────────────────────────────────────────────────────────────────
SUNO_MODELS = ["v5.5", "v5", "v4.5", "custom"]

# ─── Output Types ─────────────────────────────────────────────────────────────
OUTPUT_TYPES = [
    "1 Hour Playlist Mode",
    "Full Album Mix Mode",
    "YouTube + Distribution Package",
]

# ─── Production Modes ─────────────────────────────────────────────────────────
PRODUCTION_MODES = ["Manual", "Auto"]

# ─── App Info ─────────────────────────────────────────────────────────────────
APP_NAME = "Seoul Records Production OS"
APP_VERSION = "0.3.3"
APP_ENV = os.getenv("APP_ENV", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
