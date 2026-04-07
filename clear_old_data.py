from database.db_setup import get_connection

conn = get_connection()
cursor = conn.cursor()
cursor.execute("DELETE FROM machine_status WHERE machine_id > 1")
cursor.execute("DELETE FROM alarms WHERE machine_id > 1")
conn.commit()
cursor.close()
conn.close()
print("Old mock data cleared")
