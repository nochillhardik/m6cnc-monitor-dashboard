import os
import sys
from datetime import datetime, timezone, timedelta
from database.db_setup import get_connection
import csv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

IST = timezone(timedelta(hours=5, minutes=30))

BACKUP_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
MAX_RETRIES = 3

def ensure_backup_folder():
    os.makedirs(BACKUP_FOLDER, exist_ok=True)

def backup_machine_status(date_str):
    filename = os.path.join(BACKUP_FOLDER, f"{date_str}_machine_status.csv")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            timestamp, machine_id, machine_name, status, mode,
            program_number, program_comment, part_count, feed_rate, spindle_speed
        FROM machine_status 
        WHERE DATE(timestamp AT TIME ZONE 'UTC') = %s
        ORDER BY timestamp
    """, (date_str,))
    
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if not rows:
        print(f"No data for {date_str}")
        return None
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'machine_id', 'machine_name', 'status', 'mode',
                       'program_number', 'program_comment', 'part_count', 'feed_rate', 'spindle_speed'])
        writer.writerows(rows)
    
    print(f"Backed up {len(rows)} records to {filename}")
    return filename

def backup_alarms(date_str):
    filename = os.path.join(BACKUP_FOLDER, f"{date_str}_alarms.csv")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, timestamp, machine_id, machine_name, alarm_code, alarm_message, resolved
        FROM alarms 
        WHERE DATE(timestamp AT TIME ZONE 'UTC') = %s
        ORDER BY timestamp
    """, (date_str,))
    
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if not rows:
        print(f"No alarms for {date_str}")
        return None
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'timestamp', 'machine_id', 'machine_name', 'alarm_code', 'alarm_message', 'resolved'])
        writer.writerows(rows)
    
    print(f"Backed up {len(rows)} alarms to {filename}")
    return filename

def backup_production(date_str):
    filename = os.path.join(BACKUP_FOLDER, f"{date_str}_production.csv")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, machine_id, machine_name, program_number, program_comment,
               start_time, end_time, start_parts, end_parts, parts_produced, duration_sec, status
        FROM production_tracking 
        WHERE DATE(end_time AT TIME ZONE 'UTC') = %s
        ORDER BY end_time
    """, (date_str,))
    
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if not rows:
        print(f"No production records for {date_str}")
        return None
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'machine_id', 'machine_name', 'program_number', 'program_comment',
                       'start_time', 'end_time', 'start_parts', 'end_parts', 'parts_produced', 'duration_sec', 'status'])
        writer.writerows(rows)
    
    print(f"Backed up {len(rows)} production records to {filename}")
    return filename

def backup_yesterday():
    yesterday = datetime.now(IST) - timedelta(days=1)
    date_str = yesterday.strftime("%Y-%m-%d")
    
    print(f"=== Backing up data for {date_str} ===")
    
    for retry in range(MAX_RETRIES):
        try:
            ensure_backup_folder()
            
            status_file = backup_machine_status(date_str)
            alarms_file = backup_alarms(date_str)
            prod_file = backup_production(date_str)
            
            print(f"Backup complete for {date_str}")
            return True
            
        except Exception as e:
            print(f"Backup attempt {retry + 1} failed: {e}")
            if retry < MAX_RETRIES - 1:
                print("Retrying...")
            else:
                print("Max retries reached. Backup failed.")
                return False
    
    return False

def backup_specific_date(date_str):
    print(f"=== Backing up data for {date_str} ===")
    
    for retry in range(MAX_RETRIES):
        try:
            ensure_backup_folder()
            
            status_file = backup_machine_status(date_str)
            alarms_file = backup_alarms(date_str)
            prod_file = backup_production(date_str)
            
            print(f"Backup complete for {date_str}")
            return True
            
        except Exception as e:
            print(f"Backup attempt {retry + 1} failed: {e}")
            if retry < MAX_RETRIES - 1:
                print("Retrying...")
            else:
                print("Max retries reached. Backup failed.")
                return False
    
    return False

def list_backups():
    ensure_backup_folder()
    files = sorted(os.listdir(BACKUP_FOLDER))
    if files:
        print("\n=== Existing Backups ===")
        for f in files:
            filepath = os.path.join(BACKUP_FOLDER, f)
            size = os.path.getsize(filepath)
            print(f"  {f} ({size:,} bytes)")
    else:
        print("\nNo backups found.")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Backup CNC Monitor Data')
    parser.add_argument('--date', type=str, help='Specific date (YYYY-MM-DD). Default: yesterday')
    parser.add_argument('--list', action='store_true', help='List existing backups')
    
    args = parser.parse_args()
    
    if args.list:
        list_backups()
    elif args.date:
        backup_specific_date(args.date)
    else:
        backup_yesterday()
