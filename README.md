# CNC Monitor - Setup & Run Guide

## Folder Structure
```
cnc_monitor/
├── run_monitor.py          ← START HERE - main script
├── config.py               ← machine IPs, Supabase credentials
├── requirements.txt        ← Python packages needed
├── collector/
│   ├── data_collector.py   ← polls all machines
│   └── focas_collector.py  ← real FOCAS2 calls (pending DLL)
├── mock/
│   └── mock_data.py        ← simulated machine data (for testing)
├── database/
│   └── db_setup.py         ← creates PostgreSQL tables on Supabase
└── logs/
    └── cnc_monitor.log     ← auto-created on first run
```

## Setup Steps

### Step 1: Install Python package
```bash
pip install -r requirements.txt
```

### Step 2: Fill in Supabase credentials in config.py
```python
DB_HOST     = "db.xxxxxxxxxxxx.supabase.co"   # From Supabase project settings
DB_PASSWORD = "your-password"                  # Password you set on Supabase
```

### Step 3: Update machine IPs in config.py
```python
{"id": 1, "name": "Fanuc-01", "ip": "192.168.1.101", "port": 8193},
# ... update all 10 IPs
```

### Step 4: Run the monitor
```bash
python run_monitor.py
```

## Mock mode (no CNC required)
Set `MOCK_MODE = True` in `config.py` and run:
```bash
python run_monitor.py
```
This will use the simulated data generator in `mock/mock_data.py`, so you can test the dashboard and database pipeline without connecting any CNCs.

## Real mode (CNC connected)
Set `MOCK_MODE = False` in `config.py` and make sure `Fwlib64.dll` is present (the code loads it from the project root next to `run_monitor.py`).
