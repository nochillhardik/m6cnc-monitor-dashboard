from database.db_setup import get_connection

conn = get_connection()
cursor = conn.cursor()
cursor.execute("DELETE FROM machine_status")
cursor.execute("DELETE FROM alarms")
conn.commit()
cursor.close()
conn.close()
print("All historical data cleared. Starting fresh.")
