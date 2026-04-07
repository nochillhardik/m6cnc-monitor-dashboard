import logging
import sys
import os
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    MACHINES,
    LOG_PATH,
    SKIP_AFTER_FAILURES,
    SKIP_POLLS,
    MOCK_MODE,
    MAX_PART_DELTA_FOR_VALID_CYCLES,
    OVERRIDE_ALERT_THRESHOLD_PCT,
    OVERRIDE_ALERT_DURATION_SEC,
    MACHINE_STATUS_SAVE_ON_CHANGE_ONLY,
    MACHINE_STATUS_HEARTBEAT_SECONDS,
    MAX_STORED_PROGRAM_COMMENT_CHARS,
)
from database.db_setup import get_connection

IST = timezone(timedelta(hours=5, minutes=30))

MACHINE_STATE = {}


def _truncate_program_comment(val):
    if val is None:
        return None
    s = str(val)
    if len(s) <= MAX_STORED_PROGRAM_COMMENT_CHARS:
        return s
    return s[:MAX_STORED_PROGRAM_COMMENT_CHARS]


def _machine_status_fingerprint(data: dict) -> tuple:
    pc = _truncate_program_comment(data.get("program_comment")) or ""
    return (
        data.get("status"),
        data.get("mode"),
        data.get("program_number"),
        data.get("part_count"),
        round(float(data.get("feed_rate") or 0), 1),
        round(float(data.get("spindle_speed") or 0), 1),
        pc,
    )


def save_production_record(prod: dict):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO production_tracking 
            (machine_id, machine_name, program_number, program_comment, start_time, end_time, start_parts, end_parts, parts_produced, duration_sec, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            prod["machine_id"],
            prod["machine_name"],
            prod["program_number"],
            _truncate_program_comment(prod.get("program_comment")),
            prod["start_time"],
            prod["end_time"],
            prod["start_parts"],
            prod["end_parts"],
            prod["parts_produced"],
            prod["duration_sec"],
            prod.get("status", "completed"),
        ))
        conn.commit()
        cursor.close()
        conn.close()
        logging.info(f"PRODUCTION: {prod['machine_name']} | Program: {prod['program_number']} | Parts: {prod['parts_produced']} | Duration: {prod['duration_sec']}s")
    except Exception as e:
        logging.error(f"DB ERROR saving production for {prod.get('machine_name', 'unknown')}: {e}")

def to_ist(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)

def setup_logging():
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def save_machine_status(data: dict):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO machine_status 
            (machine_id, machine_name, status, mode, program_number, program_comment, part_count, feed_rate, spindle_speed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data["machine_id"],
            data["machine_name"],
            data["status"],
            data.get("mode"),
            data.get("program_number"),
            _truncate_program_comment(data.get("program_comment")),
            data.get("part_count"),
            data["feed_rate"],
            data["spindle_speed"],
        ))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logging.error(f"DB ERROR saving status for {data['machine_name']}: {e}")


def maybe_save_machine_status(data: dict, now_ist):
    """Insert machine_status row only if snapshot changed or heartbeat elapsed."""
    if data.get("_skipped"):
        return
    mid = data["machine_id"]
    st = MACHINE_STATE.setdefault(mid, {})
    fp = _machine_status_fingerprint(data)
    if MACHINE_STATUS_SAVE_ON_CHANGE_ONLY:
        prev_fp = st.get("last_status_fingerprint")
        prev_ts = st.get("last_status_saved_at")
        if prev_fp == fp and prev_ts is not None:
            age = (now_ist - prev_ts).total_seconds()
            if age < MACHINE_STATUS_HEARTBEAT_SECONDS:
                return
    st["last_status_fingerprint"] = fp
    st["last_status_saved_at"] = now_ist
    save_machine_status(data)


def save_alarm(data: dict):
    if data["status"] != "alarm" or data["alarm"] is None:
        return
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM alarms 
            WHERE machine_id = %s AND alarm_code = %s AND resolved = 0
        """, (data["machine_id"], data["alarm"]["code"]))
        existing = cursor.fetchone()
        if not existing:
            cursor.execute("""
                INSERT INTO alarms (machine_id, machine_name, alarm_code, alarm_message)
                VALUES (%s, %s, %s, %s)
            """, (
                data["machine_id"],
                data["machine_name"],
                data["alarm"]["code"],
                data["alarm"]["message"],
            ))
            logging.warning(f"ALARM on {data['machine_name']}: [{data['alarm']['code']}] {data['alarm']['message']}")
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logging.error(f"DB ERROR saving alarm for {data['machine_name']}: {e}")

def resolve_alarms(machine_id: int):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE alarms SET resolved = 1
            WHERE machine_id = %s AND resolved = 0 AND alarm_code != 'OVERRIDE_HIGH'
        """, (machine_id,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logging.error(f"DB ERROR resolving alarms for machine {machine_id}: {e}")

def resolve_override_alarms(machine_id: int):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE alarms SET resolved = 1
            WHERE machine_id = %s AND resolved = 0 AND alarm_code = 'OVERRIDE_HIGH'
        """, (machine_id,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logging.error(f"DB ERROR resolving override alarms for machine {machine_id}: {e}")

def save_override_alarm(machine_id: int, machine_name: str, message: str):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM alarms
            WHERE machine_id = %s AND alarm_code = %s AND resolved = 0
        """, (machine_id, "OVERRIDE_HIGH"))
        if cursor.fetchone():
            conn.commit()
            cursor.close()
            conn.close()
            return
        cursor.execute("""
            INSERT INTO alarms (machine_id, machine_name, alarm_code, alarm_message)
            VALUES (%s, %s, %s, %s)
        """, (machine_id, machine_name, "OVERRIDE_HIGH", message))
        conn.commit()
        cursor.close()
        conn.close()
        logging.warning(f"OVERRIDE ALERT on {machine_name}: {message}")
    except Exception as e:
        logging.error(f"DB ERROR saving override alarm for {machine_name}: {e}")

def update_override_alert_tracking(machine_id: int, machine_name: str, data: dict, now_ist):
    """
    If spindle % OR feed % stays above OVERRIDE_ALERT_THRESHOLD_PCT for
    OVERRIDE_ALERT_DURATION_SEC, insert OVERRIDE_HIGH into alarms (deduped while unresolved).
    """
    if data.get("_skipped") or data.get("_failed") or data.get("_connection_failed"):
        st = MACHINE_STATE.get(machine_id)
        if st:
            st["ovr_spindle_high_since"] = None
            st["ovr_feed_high_since"] = None
            MACHINE_STATE[machine_id] = st
        return

    sp = data.get("spindle_override_pct")
    fd = data.get("feed_override_pct")
    if sp is None and fd is None:
        st = MACHINE_STATE.get(machine_id)
        if st:
            st["ovr_spindle_high_since"] = None
            st["ovr_feed_high_since"] = None
            MACHINE_STATE[machine_id] = st
        return

    st = MACHINE_STATE.setdefault(machine_id, {})

    th = OVERRIDE_ALERT_THRESHOLD_PCT
    dur = OVERRIDE_ALERT_DURATION_SEC

    if sp is None:
        st["ovr_spindle_high_since"] = None
    elif sp > th:
        if st.get("ovr_spindle_high_since") is None:
            st["ovr_spindle_high_since"] = now_ist
    else:
        st["ovr_spindle_high_since"] = None

    if fd is None:
        st["ovr_feed_high_since"] = None
    elif fd > th:
        if st.get("ovr_feed_high_since") is None:
            st["ovr_feed_high_since"] = now_ist
    else:
        st["ovr_feed_high_since"] = None

    sp_since = st.get("ovr_spindle_high_since")
    fd_since = st.get("ovr_feed_high_since")
    sp_elapsed = (now_ist - sp_since).total_seconds() if sp_since else 0
    fd_elapsed = (now_ist - fd_since).total_seconds() if fd_since else 0
    trigger = (sp_since and sp_elapsed >= dur) or (fd_since and fd_elapsed >= dur)

    if trigger:
        parts = []
        if sp_since and sp_elapsed >= dur:
            parts.append(f"spindle {sp}% for {int(sp_elapsed // 60)}m")
        if fd_since and fd_elapsed >= dur:
            parts.append(f"feed {fd}% for {int(fd_elapsed // 60)}m")
        save_override_alarm(
            machine_id,
            machine_name,
            "Override >" + str(th) + "% sustained: " + ", ".join(parts),
        )

    def overrides_clear():
        if sp is not None and sp > th:
            return False
        if fd is not None and fd > th:
            return False
        return True

    if overrides_clear():
        resolve_override_alarms(machine_id)
        st["ovr_spindle_high_since"] = None
        st["ovr_feed_high_since"] = None

    MACHINE_STATE[machine_id] = st

def collect_machine_data(machine: dict, skipped: bool = False) -> dict:
    """
    Collect data from machine using FOCAS2, or return mock data when enabled.
    """
    if skipped:
        return {
            "machine_id":       machine["id"],
            "machine_name":     machine["name"],
            "status":           "offline",
            "mode":             None,
            "program_number":   None,
            "program_comment":  "",
            "part_count":       None,
            "feed_rate":        0.0,
            "spindle_speed":    0.0,
            "feed_override_pct": None,
            "spindle_override_pct": None,
            "alarm":            None,
            "_skipped":         True,
        }

    if MOCK_MODE:
        # In mock mode we intentionally do NOT import `collector.focas_collector`,
        # so there is no hard dependency on the FANUC DLLs/CNC connection.
        from mock.mock_data import get_mock_machine_data

        return get_mock_machine_data(machine["id"], machine["name"])

    try:
        from collector.focas_collector import get_focas_machine_data
        return get_focas_machine_data(machine)
    except Exception as e:
        logging.error(f"FOCAS error for {machine['name']}: {e}. Falling back to offline status.")
        return {
            "machine_id":       machine["id"],
            "machine_name":     machine["name"],
            "status":           "offline",
            "mode":             None,
            "program_number":   None,
            "program_comment":  "",
            "part_count":       None,
            "feed_rate":        0.0,
            "spindle_speed":    0.0,
            "feed_override_pct": None,
            "spindle_override_pct": None,
            "alarm":            None,
            "_failed":          True,
        }

def collect_all_machines():
    now_ist = datetime.now(IST)
    timestamp_str = now_ist.strftime("%Y-%m-%d %H:%M:%S IST")
    logging.info(f"--- Poll started at {timestamp_str} ---")

    def poll_single_machine(machine):
        machine_id = machine["id"]
        state = MACHINE_STATE.get(machine_id, {
            "fail_count": 0, 
            "skip_count": 0,
            "current_program": None,
            "current_comment": None,
            "production_start": None,
            "production_parts": None
        })
        # Production cycle counting state (valid `part_count` deltas only)
        state.setdefault("segment_parts_produced_valid", 0)
        state.setdefault("prev_parts", None)
        state.setdefault("last_part_reset_event_accum", 0)
        
        if state["skip_count"] > 0:
            state["skip_count"] -= 1
            # Avoid treating the first reading after a skip as a jump/edit.
            state["prev_parts"] = None
            MACHINE_STATE[machine_id] = state
            return collect_machine_data(machine, skipped=True), None
        
        data = collect_machine_data(machine)
        data["timestamp_ist"] = now_ist
        
        if data.get("_connection_failed") or data.get("_failed"):
            state["fail_count"] += 1
            # Avoid treating the first reading after a connection failure as a jump/edit.
            state["prev_parts"] = None
            if state["fail_count"] >= SKIP_AFTER_FAILURES:
                state["skip_count"] = SKIP_POLLS
                logging.warning(f"{machine['name']}: Offline for {state['fail_count']} polls. Skipping next {SKIP_POLLS} polls.")
            MACHINE_STATE[machine_id] = state
        else:
            if state["fail_count"] > 0 or state["skip_count"] > 0:
                logging.info(f"{machine['name']}: Back online! (was offline for {state['fail_count']} polls)")
            
            current_program = data.get("program_number")
            current_comment = data.get("program_comment")
            current_parts = data.get("part_count")
            
            if current_program and current_program != state.get("current_program"):
                if state.get("current_program") is not None and state.get("production_start") is not None:
                    # Insert a completed segment using ONLY the valid cycles counted
                    # since the last part-reset boundary.
                    segment_valid = state.get("segment_parts_produced_valid", 0)
                    last_reset_accum = state.get("last_part_reset_event_accum", 0)
                    parts_produced = segment_valid - last_reset_accum
                    start_parts = state.get("production_parts")
                    end_parts = current_parts if current_parts is not None else state.get("production_parts")
                    duration_sec = int((now_ist - state["production_start"]).total_seconds())
                    
                    if parts_produced > 0 or duration_sec > 0:
                        prod_record = {
                            "machine_id": machine_id,
                            "machine_name": machine["name"],
                            "program_number": state["current_program"],
                            "program_comment": state.get("current_comment"),
                            "start_time": state["production_start"],
                            "end_time": now_ist,
                            "start_parts": start_parts,
                            "end_parts": end_parts,
                            "parts_produced": parts_produced,
                            "duration_sec": duration_sec,
                            "status": "completed"
                        }
                        save_production_record(prod_record)
                
                state["current_program"] = current_program
                state["current_comment"] = current_comment
                state["production_start"] = now_ist
                state["production_parts"] = current_parts
                state["prev_parts"] = current_parts
                state["segment_parts_produced_valid"] = 0
                state["last_part_reset_event_accum"] = 0
            
            elif state.get("current_program") and current_parts is not None:
                prev_parts = state.get("prev_parts")
                if prev_parts is None:
                    # First valid reading for this program segment
                    state["prev_parts"] = current_parts
                    state["production_parts"] = current_parts
                else:
                    delta = current_parts - prev_parts
                    segment_valid = state.get("segment_parts_produced_valid", 0)

                    # Valid completed cycles: delta in [1, MAX]
                    if 1 <= delta <= MAX_PART_DELTA_FOR_VALID_CYCLES:
                        segment_valid += delta
                        state["segment_parts_produced_valid"] = segment_valid
                    # Operator edit/jump: large jump up OR reset down
                    elif delta < 0 or delta > MAX_PART_DELTA_FOR_VALID_CYCLES:
                        last_reset_accum = state.get("last_part_reset_event_accum", 0)
                        parts_produced = segment_valid - last_reset_accum
                        duration_sec = int((now_ist - state["production_start"]).total_seconds()) if state.get("production_start") else 0

                        if parts_produced > 0 or duration_sec > 0:
                            prod_record = {
                                "machine_id": machine_id,
                                "machine_name": machine["name"],
                                "program_number": state["current_program"],
                                "program_comment": state.get("current_comment"),
                                "start_time": state["production_start"],
                                "end_time": now_ist,
                                "start_parts": prev_parts,
                                "end_parts": current_parts,
                                "parts_produced": parts_produced,
                                "duration_sec": duration_sec,
                                "status": "part_reset"
                            }
                            save_production_record(prod_record)

                        # This part-reset row becomes the new boundary for duration + incremental parts.
                        state["last_part_reset_event_accum"] = segment_valid
                        state["production_start"] = now_ist
                        state["production_parts"] = current_parts

                    # delta == 0 is treated as "no cycles completed" and produces no event.
                    state["prev_parts"] = current_parts
            
            MACHINE_STATE[machine_id] = state
        
        return data, None

    results = []
    with ThreadPoolExecutor(max_workers=len(MACHINES)) as executor:
        futures = {executor.submit(poll_single_machine, machine): machine for machine in MACHINES}
        for future in as_completed(futures):
            result, error = future.result()
            if error:
                logging.error(error)
            elif result:
                results.append(result)

    for data in results:
        try:
            if not data.get("_skipped"):
                maybe_save_machine_status(data, now_ist)

            update_override_alert_tracking(
                data["machine_id"],
                data["machine_name"],
                data,
                now_ist,
            )

            if data["status"] == "alarm":
                save_alarm(data)
            elif not data.get("_skipped"):
                resolve_alarms(data["machine_id"])

            status_label = {
                "running":         "[RUN]",
                "idle":            "[IDLE]",
                "alarm":           "[ALARM]",
                "emergency_stop":  "[ESTOP]",
                "offline":         "[OFFLINE]",
            }.get(data["status"], "[?]")

            skipped_msg = " [SKIPPED]" if data.get("_skipped") else ""
            
            logging.info(
                f"{status_label} {data['machine_name']:12}{skipped_msg} | "
                f"Status: {data['status']:14} | "
                f"Mode: {str(data.get('mode')):8} | "
                f"Program: {str(data['program_number']):6} | "
                f"Comment: {str(data.get('program_comment', ''))[:20]} | "
                f"Parts: {str(data['part_count']):5} | "
                f"Spindle: {data['spindle_speed']:6.0f} | "
                f"Feed: {data['feed_rate']:6.0f}"
            )
        except Exception as e:
            logging.error(f"Error saving data for {data.get('machine_name', 'unknown')}: {e}")

    logging.info(f"--- Poll complete ---\n")

if __name__ == "__main__":
    setup_logging()
    collect_all_machines()
