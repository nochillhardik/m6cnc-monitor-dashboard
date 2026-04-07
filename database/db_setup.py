import psycopg2
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

def get_connection():
    """Get a connection to the PostgreSQL database on Supabase."""
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return conn

def setup_database():
    """Create all tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # Machine status table - records every poll
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS machine_status (
            id                SERIAL PRIMARY KEY,
            timestamp         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            machine_id        INTEGER NOT NULL,
            machine_name      TEXT NOT NULL,
            status            TEXT NOT NULL,
            mode              TEXT,
            program_number    INTEGER,
            program_comment   TEXT,
            part_count        INTEGER,
            feed_rate         REAL,
            spindle_speed     REAL
        )
    """)

    # Alarms table - records when alarms occur
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alarms (
            id              SERIAL PRIMARY KEY,
            timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            machine_id      INTEGER NOT NULL,
            machine_name    TEXT NOT NULL,
            alarm_code      TEXT NOT NULL,
            alarm_message   TEXT NOT NULL,
            resolved        INTEGER DEFAULT 0
        )
    """)

    # Production tracking table - records when program changes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS production_tracking (
            id                SERIAL PRIMARY KEY,
            machine_id        INTEGER NOT NULL,
            machine_name      TEXT NOT NULL,
            program_number    INTEGER NOT NULL,
            program_comment   TEXT,
            start_time       TIMESTAMP,
            end_time         TIMESTAMP,
            start_parts      INTEGER,
            end_parts        INTEGER,
            parts_produced   INTEGER,
            duration_sec     INTEGER,
            status           TEXT DEFAULT 'completed'
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Database setup complete.")

if __name__ == "__main__":
    setup_database()
