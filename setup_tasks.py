import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON_PATH = sys.executable

def run_command(cmd, description):
    print(f"\n{description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  Success: {result.stdout.strip()}")
            return True
        else:
            print(f"  Warning: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"  Error: {e}")
        return False

def setup_scheduled_tasks():
    print("=== Setting up Windows Scheduled Tasks ===")
    print(f"Python: {PYTHON_PATH}")
    print(f"Script directory: {SCRIPT_DIR}")
    
    # Task names
    backup_task = "CNCMonitor_Backup"
    delete_task = "CNCMonitor_AutoDelete"
    
    # Delete existing tasks if any
    print("\n--- Cleaning up existing tasks ---")
    subprocess.run(f'schtasks /delete /tn "{backup_task}" /f', shell=True, stderr=subprocess.DEVNULL)
    subprocess.run(f'schtasks /delete /tn "{delete_task}" /f', shell=True, stderr=subprocess.DEVNULL)
    
    # Create backup task - runs daily at midnight
    print("\n--- Creating Backup Task ---")
    backup_script = os.path.join(SCRIPT_DIR, "backup_daily.py")
    backup_cmd = f'"{PYTHON_PATH}" "{backup_script}"'
    backup_task_cmd = f'schtasks /create /tn "{backup_task}" /tr {backup_cmd} /sc daily /st 00:00 /f'
    run_command(backup_task_cmd, "Creating backup task")
    
    # Create auto-delete task - runs daily at 00:15
    print("\n--- Creating Auto-Delete Task ---")
    delete_script = os.path.join(SCRIPT_DIR, "auto_delete.py")
    delete_cmd = f'"{PYTHON_PATH}" "{delete_script}"'
    delete_task_cmd = f'schtasks /create /tn "{delete_task}" /tr {delete_cmd} /sc daily /st 00:15 /f'
    run_command(delete_task_cmd, "Creating auto-delete task")
    
    print("\n=== Scheduled Tasks Summary ===")
    
    # Verify tasks
    result = subprocess.run(f'schtasks /query /tn "{backup_task}"', shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  Backup Task: {backup_task} - CREATED")
    else:
        print(f"  Backup Task: {backup_task} - FAILED")
    
    result = subprocess.run(f'schtasks /query /tn "{delete_task}"', shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  Auto-Delete Task: {delete_task} - CREATED")
    else:
        print(f"  Auto-Delete Task: {delete_task} - FAILED")
    
    print("\n=== Task Schedule ===")
    print("  Backup: Daily at 00:00 IST")
    print("  Auto-Delete: Daily at 00:15 IST")
    
    print("\n=== Usage ===")
    print("  Manual backup: python backup_daily.py")
    print("  Manual delete: python auto_delete.py")
    print("  List backups: python backup_daily.py --list")
    print("  Backup specific date: python backup_daily.py --date 2026-04-01")
    
    print("\nTo run tasks NOW manually:")
    print(f'  schtasks /run /tn "{backup_task}"')
    print(f'  schtasks /run /tn "{delete_task}"')

def remove_scheduled_tasks():
    print("=== Removing Scheduled Tasks ===")
    backup_task = "CNCMonitor_Backup"
    delete_task = "CNCMonitor_AutoDelete"
    
    run_command(f'schtasks /delete /tn "{backup_task}" /f', "Removing backup task")
    run_command(f'schtasks /delete /tn "{delete_task}" /f', "Removing auto-delete task")
    
    print("\nAll tasks removed!")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Setup Windows Scheduled Tasks for CNC Monitor')
    parser.add_argument('--remove', action='store_true', help='Remove scheduled tasks')
    
    args = parser.parse_args()
    
    if args.remove:
        remove_scheduled_tasks()
    else:
        setup_scheduled_tasks()
