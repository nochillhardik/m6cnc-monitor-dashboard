from database.db_setup import get_connection
from datetime import datetime, timezone, timedelta
import csv

IST = timezone(timedelta(hours=5, minutes=30))

def to_ist(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)

def export_to_csv(filename="machine_data.csv"):
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
    """)
    
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Machine', 'Status', 'Mode', 'Program', 'Comment', 'Parts', 'Feed (mm/min)', 'Spindle (RPM)', 'Timestamp (IST)'])
        for row in rows:
            ts_ist = to_ist(row[8]).strftime('%Y-%m-%d %H:%M:%S')
            writer.writerow([
                row[0],  # machine_name
                row[1],  # status
                row[2] or '',  # mode
                row[3] or '',  # program_number
                row[4] or '',  # program_comment
                row[5] or '',  # part_count
                f"{row[6]:.1f}" if row[6] else '0',  # feed_rate
                f"{row[7]:.1f}" if row[7] else '0',  # spindle_speed
                ts_ist  # timestamp IST
            ])
    
    print(f"Exported {len(rows)} rows to {filename}")

if __name__ == "__main__":
    export_to_csv()
