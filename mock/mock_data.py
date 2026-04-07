import random
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ============================================================
# MOCK DATA SIMULATOR
# - Generates realistic CNC snapshots (running/idle/alarm/offline)
# - Keeps per-machine state so program changes and part resets can be detected
# ============================================================

# Realistic alarm codes for Fanuc OiTF
FANUC_ALARMS = [
    ("PS0010", "IMPROPER G-CODE"),
    ("PS0011", "FEEDRATE NOT FOUND"),
    ("OT0500", "OVER TRAVEL: +X"),
    ("OT0501", "OVER TRAVEL: -X"),
    ("OT0502", "OVER TRAVEL: +Z"),
    ("SP1241", "SPINDLE SPEED ERROR"),
    ("SV0401", "SERVO ALARM: V-READY OFF"),
    ("SV0410", "SERVO ALARM: EXCESS ERROR"),
]

MODES = ["MEM", "MDI", "EDIT", "JOG", "HANDLE"]
PROGRAM_COMMENTS = [
    "JOB-ALPHA",
    "JOB-BETA",
    "JOB-GAMMA",
    "OP-DRILL-01",
    "OP-MILL-02",
    "OP-TURN-03",
    "OP-GRIND-04",
]

# Per-machine state for stable segments
_machine_state = {}


def _init_machine(machine_id: int, machine_name: str) -> dict:
    return {
        "machine_name": machine_name,
        "part_count": random.randint(0, 200),
        "program_number": random.randint(1000, 9999),
        "program_comment": random.choice(PROGRAM_COMMENTS),
        "mode": random.choice(MODES),
        # How many polls before we change the program again (while running/idle)
        "program_segment_remaining": random.randint(5, 12),
        # Keep offline for a few polls when it happens
        "offline_ticks_remaining": 0,
        # Override simulator: counts polls while both > 105% (15s polls → ~21 = 5+ min)
        "override_high_remaining": 0,
    }


def get_mock_machine_data(machine_id: int, machine_name: str) -> dict:
    """
    Returns simulated machine data for a given machine.

    The generator is stateful so the monitor can detect:
    - "Program Change": program_number changes after several running/idle polls
    - "Part Reset": occasional large part_count jumps/resets while running
    """
    st = _machine_state.get(machine_id)
    if st is None:
        st = _init_machine(machine_id, machine_name)
        _machine_state[machine_id] = st
    else:
        st["machine_name"] = machine_name

    # Decide machine status for this poll
    if st["offline_ticks_remaining"] > 0:
        st["offline_ticks_remaining"] -= 1
        status = "offline"
    else:
        rand = random.random()
        if rand < 0.70:
            status = "running"
        elif rand < 0.85:
            status = "idle"
        elif rand < 0.95:
            status = "alarm"
        else:
            status = "offline"
            st["offline_ticks_remaining"] = random.randint(2, 4)

    # Program + mode (only meaningful in running/idle)
    if status in ["running", "idle"]:
        if st["program_segment_remaining"] <= 0:
            st["program_number"] = random.randint(1000, 9999)
            st["program_comment"] = random.choice(PROGRAM_COMMENTS)
            st["mode"] = random.choice(MODES)
            st["program_segment_remaining"] = random.randint(5, 12)
        else:
            st["program_segment_remaining"] -= 1

        program_number = st["program_number"]
        program_comment = st["program_comment"]
        mode = st["mode"]
    else:
        program_number = None
        program_comment = ""
        mode = None

    # Part count + speed/feed + overrides (%)
    feed_rate = 0.0
    spindle_speed = 0.0
    part_count = None
    alarm = None
    feed_override_pct = None
    spindle_override_pct = None

    if status == "running":
        # Normal part completion
        if random.random() < 0.30:
            st["part_count"] += random.randint(1, 3)

        # Occasional large jump/reset to trigger "Part Reset" event detection
        if random.random() < 0.06:
            if random.random() < 0.5:
                st["part_count"] = random.randint(0, 10)  # reset-ish
            else:
                st["part_count"] += random.randint(20, 80)  # jump-ish

        part_count = st["part_count"]
        feed_rate = round(random.uniform(100, 800), 1)
        spindle_speed = round(random.uniform(500, 3000), 1)

        if st["override_high_remaining"] > 0:
            st["override_high_remaining"] -= 1
            feed_override_pct = random.randint(106, 120)
            spindle_override_pct = random.randint(106, 120)
        else:
            feed_override_pct = random.randint(80, 105)
            spindle_override_pct = random.randint(80, 105)
            if random.random() < 0.04:
                st["override_high_remaining"] = 22

    elif status == "idle":
        part_count = st["part_count"]
        feed_override_pct = 100
        spindle_override_pct = 100

    elif status == "alarm":
        alarm_code, alarm_message = random.choice(FANUC_ALARMS)
        alarm = {
            "code": alarm_code,
            "message": alarm_message,
        }
        # Keep program/part invalid in alarm snapshots to avoid production event noise.
        part_count = None

    elif status == "offline":
        # Keep everything invalid in offline snapshots.
        part_count = None

    return {
        "machine_id": machine_id,
        "machine_name": machine_name,
        "status": status,
        "mode": mode,
        "program_number": program_number,
        "program_comment": program_comment,
        "part_count": part_count,
        "feed_rate": feed_rate,
        "spindle_speed": spindle_speed,
        "feed_override_pct": feed_override_pct,
        "spindle_override_pct": spindle_override_pct,
        "alarm": alarm,
    }
