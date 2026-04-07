# ============================================================
# CNC MONITOR - MACHINE CONFIGURATION
# Edit this file to match your actual machine IPs later
# ============================================================

MACHINES = [
    {"id": 1, "name": "CNC-8",  "ip": "192.168.1.118", "port": 8193},
    {"id": 2, "name": "CNC-4",  "ip": "192.168.1.104", "port": 8193},
    {"id": 3, "name": "CNC-5",  "ip": "192.168.1.105", "port": 8193},
    {"id": 4, "name": "CNC-9",  "ip": "192.168.1.109", "port": 8193},
    {"id": 5, "name": "CNC-12", "ip": "192.168.1.112", "port": 8193},
]

# How often to collect data (in seconds)
# 300 = 5 minutes
POLL_INTERVAL_SECONDS = 15

# Database size: skip identical consecutive machine_status snapshots (still save on change
# or after this many seconds as a heartbeat so history does not go silent forever).
MACHINE_STATUS_SAVE_ON_CHANGE_ONLY = True
MACHINE_STATUS_HEARTBEAT_SECONDS = 300

# Cap program comment length stored in Postgres (reduces row size on high-frequency inserts).
MAX_STORED_PROGRAM_COMMENT_CHARS = 120

# ============================================================
# MOCK MODE (no CNC required)
# When True, the app uses simulated CNC data from `mock/mock_data.py`.
# When False, it polls real machines using the FANUC FOCAS2 DLL.
# ============================================================
MOCK_MODE = False

# Production counting: assume the CNC increments `part_count` by 1 per completed cycle.
# If the part counter changes by a small positive amount (1..this threshold), we count it as valid
# completed cycles. Larger jumps (or resets) are treated as operator edits and ignored for counting.
MAX_PART_DELTA_FOR_VALID_CYCLES = 10

# Override alert: fires if spindle % OR feed % stays above threshold continuously
# for this long (one alert episode; resolved when every available reading is <= threshold).
OVERRIDE_ALERT_THRESHOLD_PCT = 105
OVERRIDE_ALERT_DURATION_SEC = 300  # 5 minutes

# OEE page (pages/3_OEE_Insights.py): sandwich timeline + downtime episode chart
# Tune these after you have real machine data.
DOWNTIME_MIN_THRESHOLD = 15  # minutes spindle=0 before a bar counts as a downtime episode
SANDWICH_BIN_MINUTES = 1  # minute buckets for red/green/blue/gray timeline
SANDWICH_DOWNTIME_SPINDLE_THRESHOLD = 0  # red when spindle <= this
SANDWICH_MEM_MODE_VALUES = ("MEM",)  # green when spindle above threshold and mode in this tuple
SANDWICH_MIN_STATE_DURATION_MINUTES = 0  # collapse state flips shorter than this many minutes (0 = off)

# Skip mechanism for offline machines
SKIP_AFTER_FAILURES = 3   # Skip after 3 consecutive connection failures
SKIP_POLLS = 5            # Skip next 5 polls before retrying

# ============================================================
# SUPABASE POSTGRESQL DATABASE SETTINGS
# Fill these in after creating your Supabase project
# ============================================================
DB_HOST     = "aws-1-ap-northeast-1.pooler.supabase.com"
DB_PORT     = 5432
DB_NAME     = "postgres"
DB_USER     = "postgres.pkerudvzegvltzogjhrb"
DB_PASSWORD = "CF4TTW9nTrPIFZBx"

# Log file location
LOG_PATH = "logs/cnc_monitor.log"
