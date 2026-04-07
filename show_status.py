from database.db_setup import get_connection
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

def to_ist(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)

def show_latest():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            machine_name,
            status,
            mode,
            program_number,
            part_count,
            feed_rate,
            spindle_speed,
            timestamp
        FROM machine_status 
        ORDER BY timestamp DESC
        LIMIT 20
    """)
    
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 95)
    print(f"{'Machine':<10} {'Status':<15} {'Mode':<8} {'Program':<10} {'Parts':<8} {'Feed':<10} {'Spindle':<10} {'Timestamp (IST)'}")
    print("=" * 95)
    
    seen = set()
    for row in rows:
        machine_name = row[0]
        if machine_name in seen:
            continue
        seen.add(machine_name)
        
        status = row[1]
        mode = str(row[2]) if row[2] else "-"
        program = str(row[3]) if row[3] else "-"
        parts = str(row[4]) if row[4] else "-"
        feed = f"{row[5]:.0f}" if row[5] else "0"
        spindle = f"{row[6]:.0f}" if row[6] else "0"
        ts_ist = to_ist(row[7]).strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"{machine_name:<10} {status:<15} {mode:<8} {program:<10} {parts:<8} {feed:<10} {spindle:<10} {ts_ist}")
    
    print("=" * 95)

if __name__ == "__main__":
    show_latest()
