# Database storage optimization (2 GB budget)

## What was implemented in code

### 1. Fewer `machine_status` rows (largest growth driver)

- **Change-on-save + heartbeat** in `collector/data_collector.py` via `maybe_save_machine_status()`.
- A new row is written when the **snapshot fingerprint** changes (status, mode, program #, part count, feed, spindle, truncated comment), **or** when **`MACHINE_STATUS_HEARTBEAT_SECONDS`** has passed with no change (default **300 s**).
- Tuning in `config.py`:
  - `MACHINE_STATUS_SAVE_ON_CHANGE_ONLY` (default `True`) — set `False` to revert to every-poll inserts.
  - `MACHINE_STATUS_HEARTBEAT_SECONDS` — lower = more rows; higher = less history granularity during idle periods.

**Trade-off:** “Last poll” on the dashboard can reflect the latest **saved** snapshot, not every poll, when the machine is unchanged. OEE/downtime resolution is coarser between heartbeats if nothing changes.

### 2. Shorter program comments in Postgres

- `program_comment` is truncated to **`MAX_STORED_PROGRAM_COMMENT_CHARS`** (default **120**) on insert into `machine_status` and `production_tracking`.

**Trade-off:** Very long comments are clipped in the DB (UI can still show full text if gathered live from the CNC elsewhere in future).

### 3. Existing retention script

- `auto_delete.py` deletes old `machine_status`, resolved `alarms`, and `production_tracking` by age (`RETENTION_DAYS`, default 7). Run on a schedule if you want a hard cap on history.

## What was not changed (optional next steps)

- **Indexes:** Adding indexes speeds queries but **uses disk**. Add only for slow queries you actually run.
- **Downsampling / rollups:** A nightly job could aggregate `machine_status` into hourly summaries and delete raw rows (bigger behavior change).
- **VARCHAR vs TEXT:** Minor savings; not prioritized here.

## Monitoring disk usage (Supabase / Postgres)

- Watch table sizes in the Supabase dashboard or run (if you have SQL access):

  ```sql
  SELECT relname, pg_total_relation_size(relid) AS bytes
  FROM pg_catalog.pg_statio_user_tables
  ORDER BY bytes DESC;
  ```

## Rough order of table growth

1. `machine_status` — high frequency (now reduced by change-only + heartbeat).
2. `production_tracking` — event-driven (moderate).
3. `alarms` — usually low volume.
