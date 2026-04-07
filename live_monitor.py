from database.db_setup import get_connection
from datetime import datetime, timezone, timedelta
import sys
import time

IST = timezone(timedelta(hours=5, minutes=30))

def get_latest_data():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            machine_name,
            status,
            mode,
            program_number,
            program_comment,
            part_count,
            feed_rate,
            spindle_speed,
            timestamp
        FROM machine_status 
        ORDER BY timestamp DESC
        LIMIT 50
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def to_ist(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)

def clear_screen():
    print("\033[2J\033[H", end="")

def format_status(status):
    colors = {
        "running":         "RUNNING",
        "idle":            "IDLE",
        "alarm":           "ALARM",
        "emergency_stop":  "ESTOP",
        "offline":         "OFFLINE",
    }
    return colors.get(status, status.upper())

def display_live():
    while True:
        clear_screen()
        now = datetime.now(IST)
        print("=" * 90)
        print(f"  CNC MONITOR - Live View  |  {now.strftime('%Y-%m-%d %H:%M:%S IST')}")
        print("=" * 90)
        sys.stdout.flush()
        
        rows = get_latest_data()
        
        if not rows:
            print("\n  No data available yet. Waiting for first poll...\n")
            print("=" * 90)
            sys.stdout.flush()
            time.sleep(5)
            continue
        
        print(f"\n  {'Machine':<10} {'Status':<10} {'Mode':<8} {'Program':<8} {'Comment':<20} {'Parts':<6} {'Feed':<7} {'Spindle':<8} {'Time'}")
        print("-" * 100)
        sys.stdout.flush()
        
        for row in rows:
            machine_name = row[0]
            status = row[1]
            mode = row[2] or "-"
            program = str(row[3]) if row[3] else "-"
            comment = str(row[4])[:20] if row[4] else ""
            parts = str(row[5]) if row[5] else "-"
            feed = f"{row[6]:.0f}" if row[6] else "0"
            spindle = f"{row[7]:.0f}" if row[7] else "0"
            ts = to_ist(row[8]).strftime("%H:%M:%S")
            
            print(f"  {machine_name:<10} {format_status(status):<10} {mode:<8} {program:<8} {comment:<20} {parts:<6} {feed:<7} {spindle:<8} {ts}")
            sys.stdout.flush()
        
        print("-" * 90)
        print(f"  Showing last {len(rows)} polls")
        print("  Press Ctrl+C to exit")
        print("=" * 90)
        sys.stdout.flush()
        
        time.sleep(15)

if __name__ == "__main__":
    try:
        display_live()
    except KeyboardInterrupt:
        print("\n\nExiting live monitor...")
        sys.exit(0)
