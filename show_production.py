from database.db_setup import get_connection
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

def to_ist(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)

def show_production():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            machine_name,
            program_number,
            program_comment,
            start_time,
            end_time,
            start_parts,
            end_parts,
            parts_produced,
            duration_sec,
            status
        FROM production_tracking 
        ORDER BY end_time DESC
        LIMIT 20
    """)
    
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if not rows:
        print("\nNo production records yet.")
        print("Production will be recorded when program changes.")
        return
    
    print("\n" + "=" * 120)
    print(f"{'Machine':<10} {'Program':<8} {'Comment':<25} {'Start':<20} {'End':<20} {'Parts':<8} {'Duration':<10} {'Status'}")
    print("=" * 120)
    
    for row in rows:
        machine = row[0]
        program = row[1]
        comment = str(row[2])[:24] if row[2] else ""
        start = to_ist(row[3]).strftime('%Y-%m-%d %H:%M') if row[3] else "-"
        end = to_ist(row[4]).strftime('%Y-%m-%d %H:%M') if row[4] else "-"
        parts = f"{row[7]}" if row[7] else "0"
        duration = f"{row[8]}s" if row[8] else "-"
        status = row[9]
        
        print(f"{machine:<10} {program:<8} {comment:<25} {start:<20} {end:<20} {parts:<8} {duration:<10} {status}")
    
    print("=" * 120)
    print(f"Total records: {len(rows)}")

if __name__ == "__main__":
    show_production()
