import os
import sys
from datetime import datetime, timezone, timedelta
from database.db_setup import get_connection

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

IST = timezone(timedelta(hours=5, minutes=30))

RETENTION_DAYS = 7

def cleanup_old_data():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Calculate cutoff date
    cutoff_date = datetime.now(IST) - timedelta(days=RETENTION_DAYS)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"=== Auto-Delete: Removing data older than {RETENTION_DAYS} days ===")
    print(f"Cutoff: {cutoff_str} IST")
    
    # Delete old machine_status records
    cursor.execute("""
        DELETE FROM machine_status 
        WHERE timestamp < %s
    """, (cutoff_date,))
    deleted_status = cursor.rowcount
    
    print(f"Deleted {deleted_status} old machine_status records")
    
    # Delete old alarm records (keep resolved alarms longer, delete unresolve ones)
    cursor.execute("""
        DELETE FROM alarms 
        WHERE timestamp < %s AND resolved = 1
    """, (cutoff_date,))
    deleted_alarms = cursor.rowcount
    
    print(f"Deleted {deleted_alarms} old resolved alarm records")
    
    # Delete old production records
    cursor.execute("""
        DELETE FROM production_tracking 
        WHERE end_time < %s
    """, (cutoff_date,))
    deleted_prod = cursor.rowcount
    
    print(f"Deleted {deleted_prod} old production records")
    
    # Vacuum to reclaim space
    try:
        cursor.execute("VACUUM")
        print("Database vacuumed")
    except:
        pass
    
    conn.commit()
    
    # Get remaining counts
    cursor.execute("SELECT COUNT(*) FROM machine_status")
    remaining_status = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM alarms")
    remaining_alarms = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM production_tracking")
    remaining_prod = cursor.fetchone()[0]
    
    print(f"\nRemaining records:")
    print(f"  machine_status: {remaining_status}")
    print(f"  alarms: {remaining_alarms}")
    print(f"  production_tracking: {remaining_prod}")
    
    cursor.close()
    conn.close()
    
    print("\nAuto-delete complete!")
    return True

if __name__ == "__main__":
    try:
        cleanup_old_data()
    except Exception as e:
        print(f"Auto-delete failed: {e}")
        sys.exit(1)
