# CNC Machine Monitoring System - Migration Guide
## Version: m3.1

---

## Project Overview

**Purpose:** Real-time CNC machine monitoring using FANUC FOCAS2 protocol

**What it does:**
- Polls FANUC CNC machines every 15 seconds
- Collects: status, mode, program number, program comment, part count, spindle speed, feed rate
- Stores data in PostgreSQL (Supabase)
- Displays live monitoring view

**Machines Monitored:**
| ID | Name | IP | Port | Model |
|----|------|-----|------|-------|
| 1 | CNC-8 | 192.168.1.118 | 8193 | FANUC Oi-TF |
| 2 | CNC-4 | 192.168.1.104 | 8193 | FANUC Oi-TF |
| 3 | CNC-5 | 192.168.1.105 | 8193 | FANUC Oi-TF |
| 4 | CNC-9 | 192.168.1.109 | 8193 | FANUC Oi-TF |
| 5 | CNC-12 | 192.168.1.112 | 8193 | FANUC Oi-TF |

---

## File Structure

```
m3/
├── config.py                 # Machine IPs, DB settings, skip config
├── run_monitor.py            # Main entry point
├── collector/
│   ├── data_collector.py    # Data collection & DB saving
│   └── focas_collector.py    # FOCAS2 API calls
├── database/
│   └── db_setup.py          # Database schema
├── live_monitor.py           # Live terminal view
├── export_to_excel.py        # CSV export
├── show_status.py            # Quick status check
├── clear_all_data.py         # Clear DB
├── Fwlib64.dll               # FANUC FOCAS2 library (64-bit)
├── fwlib0DN64.dll            # Alternative FANUC DLL
├── fwlib30i64.dll            # Alternative FANUC DLL
└── logs/
    └── cnc_monitor.log       # Application logs
```

---

## Key Technologies

| Component | Technology |
|----------|------------|
| Language | Python 3.x |
| CNC Protocol | FANUC FOCAS2 (port 8193) |
| Database | PostgreSQL (Supabase) |
| Platform | Windows |
| DLL | Fwlib64.dll (64-bit) |

---

## Data Collected

| Field | Description | Source |
|-------|-------------|--------|
| status | running, idle, alarm, emergency_stop, offline | Calculated from spindle/feed |
| mode | MDI, MEM, EDIT, JOG, HANDLE, HOME, REF | cnc_statinfo |
| program_number | NC program number (e.g., 231) | cnc_rdprgnum |
| program_comment | Program header comment | cnc_rdexecprog |
| part_count | Parts completed | Parameter 6711 |
| spindle_speed | RPM | cnc_acts |
| feed_rate | mm/min | cnc_actf |
| timestamp | IST (UTC+5:30) | Python datetime |

---

## Database Schema

### Table: machine_status
```sql
CREATE TABLE machine_status (
    id                SERIAL PRIMARY KEY,
    timestamp         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    machine_id        INTEGER NOT NULL,
    machine_name      TEXT NOT NULL,
    status           TEXT NOT NULL,
    mode             TEXT,
    program_number   INTEGER,
    program_comment  TEXT,
    part_count       INTEGER,
    feed_rate        REAL,
    spindle_speed    REAL
);
```

### Table: alarms
```sql
CREATE TABLE alarms (
    id              SERIAL PRIMARY KEY,
    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    machine_id      INTEGER NOT NULL,
    machine_name    TEXT NOT NULL,
    alarm_code      TEXT NOT NULL,
    alarm_message   TEXT NOT NULL,
    resolved        INTEGER DEFAULT 0
);
```

---

## Configuration (config.py)

```python
MACHINES = [
    {"id": 1, "name": "CNC-8",  "ip": "192.168.1.118", "port": 8193},
    {"id": 2, "name": "CNC-4",  "ip": "192.168.1.104", "port": 8193},
    {"id": 3, "name": "CNC-5",  "ip": "192.168.1.105", "port": 8193},
    {"id": 4, "name": "CNC-9",  "ip": "192.168.1.109", "port": 8193},
    {"id": 5, "name": "CNC-12", "ip": "192.168.1.112", "port": 8193},
]

POLL_INTERVAL_SECONDS = 15
SKIP_AFTER_FAILURES = 3    # Skip after 3 consecutive failures
SKIP_POLLS = 5            # Skip next 5 polls before retry

DB_HOST = "aws-1-ap-northeast-1.pooler.supabase.com"
DB_PORT = 5432
DB_NAME = "postgres"
DB_USER = "postgres.pkerudvzegvltzogjhrb"
DB_PASSWORD = "CF4TTW9nTrPIFZBx"
```

---

## Status Logic

```python
def decode_status(stat, spindle_speed, feed_rate):
    if stat.emergency == 1:
        return "emergency_stop"
    if stat.alarm == 1:
        return "alarm"
    if spindle_speed != 0 or feed_rate != 0:
        return "running"
    return "idle"
```

---

## CNC Mode Mapping (FANUC Oi-TF)

| aut value | Mode |
|-----------|------|
| 0 | MDI |
| 1 | MEM |
| 2 | RMT |
| 3 | EDIT |
| 4 | HANDLE |
| 5 | JOG |
| 6 | INC |
| 7 | TEACH |
| 8 | MDI_JOG |
| 9 | REF_HOME |

---

## Running the System

### Start Monitoring
```bash
python run_monitor.py
```

### Live View (separate terminal)
```bash
python live_monitor.py
```

### Export to CSV
```bash
python export_to_excel.py
```

### Quick Status
```bash
python show_status.py
```

---

## Important Notes for New AI

### 1. FOCAS2 API
- Uses `Fwlib64.dll` for 64-bit Windows
- Connection timeout: 2 seconds
- Function signatures defined using ctypes
- Some functions may not work on all CNC models

### 2. Program Comment Extraction
- Uses `cnc_rdexecprog` function (not cnc_rdprogline2)
- Extracts text from parentheses in NC program header
- Returns empty if program has no comment

### 3. Skip Mechanism
- After 3 consecutive connection failures, machine is skipped for 5 polls
- Reduces polling time for offline machines
- Automatically retries after skip period

### 4. Timezone
- All timestamps stored in UTC
- Displayed in IST (UTC+5:30)
- Database uses PostgreSQL TIMESTAMP

### 5. DLL Compatibility
- `Fwlib64.dll` - Generic 64-bit (used)
- `fwlib0DN64.dll` - For 0i-D/F models
- `fwlib30i64.dll` - For 30i series

---

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Connection fails with code -16 | Check CNC IP address, Ethernet settings |
| Program comment empty | Program may not have header comment |
| cnc_rdactdt not found | Function not in DLL, skip tool data |
| Slow polling | Skip mechanism helps, reduce timeout |

---

## Verified Working Data Points

| Data | Verified | Notes |
|------|----------|-------|
| Status | Yes | Based on spindle/feed |
| Mode | Yes | aut=0-9 mapping confirmed |
| Program Number | Yes | data>>16 extraction |
| Program Comment | Yes | Using cnc_rdexecprog |
| Part Count | Yes | Param 6711 |
| Spindle Speed | Yes | cnc_acts |
| Feed Rate | Yes | cnc_actf |

---

## Future Enhancements

- [ ] Add "setting up" status (conditions TBD)
- [ ] Tool number extraction (via parameter)
- [ ] Skip mechanism for offline machines (IMPLEMENTED)
- [ ] Web dashboard
- [ ] Email/SMS alerts
- [ ] OEE calculation

---

## Contact / Notes

- System built for FANUC Oi-TF CNC machines
- Supabase PostgreSQL database
- Real-time monitoring with 15-second intervals

---

**Document Version:** m3.1  
**Last Updated:** 2026-04-02
