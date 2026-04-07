import streamlit as st
from datetime import datetime, timezone, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db_setup import get_connection
from streamlit_autorefresh import st_autorefresh
from display_format import to_ist, format_ist_datetime

IST = timezone(timedelta(hours=5, minutes=30))

st.set_page_config(
    page_title="CNC Monitor",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .machine-card {
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    .running { background-color: #e8f5e9; border-left: 5px solid #4caf50; }
    .idle { background-color: #fff8e1; border-left: 5px solid #ffc107; }
    .alarm { background-color: #ffebee; border-left: 5px solid #f44336; }
    .offline { background-color: #eceff1; border-left: 5px solid #9e9e9e; }
    .event-item { padding: 5px 0; border-bottom: 1px solid #eee; }
    .reset-event { color: #ff9800; font-weight: bold; }
    .program-event { color: #2196f3; }
    .override-event { color: #7b1fa2; font-weight: bold; }
    .cnc-alarm-event { color: #c62828; font-weight: bold; }
</style>
""",
    unsafe_allow_html=True,
)


def get_mode_last_changed_map():
    """Latest timestamp when each machine entered its current mode (from machine_status history)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            WITH latest AS (
                SELECT DISTINCT ON (machine_id) machine_id, mode AS cur_mode
                FROM machine_status
                ORDER BY machine_id, timestamp DESC
            ),
            lags AS (
                SELECT machine_id, timestamp, mode,
                    LAG(mode) OVER (
                        PARTITION BY machine_id ORDER BY timestamp ASC
                    ) AS prev_mode
                FROM machine_status
            ),
            entries AS (
                SELECT machine_id, timestamp, mode
                FROM lags
                WHERE mode IS NOT NULL
                  AND (prev_mode IS DISTINCT FROM mode)
            )
            SELECT l.machine_id, MAX(e.timestamp) AS mode_since
            FROM latest l
            INNER JOIN entries e
                ON e.machine_id = l.machine_id AND e.mode = l.cur_mode
            WHERE l.cur_mode IS NOT NULL
            GROUP BY l.machine_id
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return {int(r[0]): r[1] for r in rows if r[1] is not None}
    except Exception:
        return {}


def get_latest_status():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                machine_id,
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
            ORDER BY machine_id, timestamp DESC
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        data = []
        seen = set()
        for row in rows:
            machine_id = row[0]
            if machine_id in seen:
                continue
            seen.add(machine_id)
            data.append(
                {
                    "machine_id": machine_id,
                    "machine": row[1],
                    "status": row[2],
                    "mode": row[3] or "-",
                    "program": str(row[4]) if row[4] else "-",
                    "program_name": str(row[5])[:40] if row[5] else "-",
                    "parts": row[6] if row[6] else 0,
                    "feed": row[7] if row[7] else 0,
                    "spindle": row[8] if row[8] else 0,
                    "last_update": format_ist_datetime(row[9], include_date=False)
                    if row[9]
                    else "-",
                }
            )
        return data
    except Exception as e:
        st.error(f"Database error: {e}")
        return []


def get_machine_alerts(machine_id, row_limit=100):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                program_number,
                program_comment,
                start_time,
                end_time,
                start_parts,
                end_parts,
                parts_produced,
                duration_sec,
                status
            FROM production_tracking
            WHERE machine_id = %s
            ORDER BY end_time DESC NULLS LAST
            LIMIT %s
            """,
            (machine_id, row_limit),
        )
        prod_rows = cursor.fetchall()

        cursor.execute(
            """
            SELECT alarm_code, alarm_message, timestamp, resolved
            FROM alarms
            WHERE machine_id = %s
            ORDER BY timestamp DESC
            LIMIT %s
            """,
            (machine_id, row_limit),
        )
        alarm_rows = cursor.fetchall()
        cursor.close()
        conn.close()

        alerts = []

        for row in prod_rows:
            start_dt = to_ist(row[2]) if row[2] else None
            end_dt = to_ist(row[3]) if row[3] else None
            sort_ts = end_dt or start_dt
            event_type = "Program Change" if row[8] == "completed" else "Part Reset"
            alerts.append(
                {
                    "source": "production",
                    "sort_ts": sort_ts,
                    "program": str(row[0]) if row[0] else "-",
                    "program_name": str(row[1])[:30] if row[1] else "-",
                    "start_time": format_ist_datetime(row[2], include_date=False)
                    if start_dt
                    else "-",
                    "end_time": format_ist_datetime(row[3], include_date=False)
                    if end_dt
                    else "-",
                    "parts": row[6] if row[6] else 0,
                    "duration": row[7] if row[7] else 0,
                    "event_type": event_type,
                    "start_parts": row[4] if row[4] else 0,
                    "end_parts": row[5] if row[5] else 0,
                }
            )

        for row in alarm_rows:
            ts = row[2]
            alerts.append(
                {
                    "source": "alarm",
                    "sort_ts": to_ist(ts) if ts else None,
                    "alarm_code": row[0],
                    "alarm_message": row[1],
                    "alarm_time": format_ist_datetime(ts, include_date=True) if ts else "-",
                    "resolved": bool(row[3]),
                }
            )

        alerts.sort(
            key=lambda x: x["sort_ts"].timestamp() if x["sort_ts"] else 0.0,
            reverse=True,
        )
        return alerts
    except Exception as e:
        st.error(f"Database error (alerts): {e}")
        return []


def render_alert_row(alert):
    if alert["source"] == "production":
        ev = alert["event_type"]
        if ev == "Part Reset":
            st.markdown(
                f"<div class='reset-event'>⚡ {ev}: +{alert['parts']} parts "
                f"({alert['start_parts']}→{alert['end_parts']})</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div class='program-event'>📋 {alert['program']}: +{alert['parts']} parts "
                f"({alert['start_time']} – {alert['end_time']})</div>",
                unsafe_allow_html=True,
            )
        st.caption(f"{alert['program_name'][:25]} | {format_duration(alert['duration'])}")
    else:
        code = alert["alarm_code"]
        msg = (alert["alarm_message"] or "")[:120]
        if code == "OVERRIDE_HIGH":
            st.markdown(
                f"<div class='override-event'>🎛️ Override alert: {msg}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div class='cnc-alarm-event'>🔧 [{code}] {msg}</div>",
                unsafe_allow_html=True,
            )
        res = "resolved" if alert["resolved"] else "active"
        st.caption(f"{alert['alarm_time']} · {res}")


def get_total_parts_for_program(machine_id, program_number):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(parts_produced), 0)
            FROM production_tracking
            WHERE machine_id = %s AND program_number = %s
            """,
            (machine_id, program_number),
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result[0] if result else 0
    except Exception:
        return 0


def get_status_icon(status):
    icons = {
        "running": "🟢 Running",
        "idle": "🟡 Idle",
        "alarm": "🔴 Alarm",
        "emergency_stop": "🔴 E-Stop",
        "offline": "⚪ Offline",
    }
    return icons.get(status, "⚪ Unknown")


def format_duration(seconds):
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    return f"{seconds // 3600}h {(seconds % 3600) // 60}m"


def main():
    st.title("🏭 CNC Monitor")
    st.markdown("### Real-time Machine Status")

    st_autorefresh(interval=300000, key="dashboard_autorefresh")

    if "refresh_key" not in st.session_state:
        st.session_state.refresh_key = 0

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🔄 Refresh", type="primary", use_container_width=True):
            st.session_state.refresh_key += 1
    with col2:
        st.markdown(
            f"<div style='text-align: right; color: gray;'>Last update: "
            f"{format_ist_datetime(datetime.now(IST), include_date=True)} IST</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    mode_since_map = get_mode_last_changed_map()
    data = get_latest_status()

    def machine_rows(machines, per_row=3):
        for i in range(0, len(machines), per_row):
            yield machines[i : i + per_row]

    if data:
        for row_machines in machine_rows(data, 3):
            cols = st.columns(3)
            for j, machine in enumerate(row_machines):
                status = machine["status"]
                card_class = (
                    status
                    if status in ["running", "idle", "alarm", "offline"]
                    else "offline"
                )
                alerts = get_machine_alerts(machine["machine_id"])
                mode_since_raw = mode_since_map.get(machine["machine_id"])
                mode_since_txt = (
                    format_ist_datetime(mode_since_raw, include_date=True)
                    if mode_since_raw
                    else "—"
                )

                with cols[j]:
                    st.markdown(f"<div class='{card_class}'>", unsafe_allow_html=True)
                    st.markdown(f"#### {machine['machine']}")
                    st.caption(
                        f"{get_status_icon(status)} · Mode: **{machine['mode']}** · since {mode_since_txt}"
                    )
                    pn = str(machine["program_name"])
                    st.caption(
                        f"Prg **{machine['program']}** · {pn[:28]}{'…' if len(pn) > 28 else ''}"
                    )
                    m1, m2 = st.columns(2)
                    with m1:
                        st.metric("Current Part Count", machine["parts"])
                    with m2:
                        if machine["program"] != "-":
                            try:
                                tp = get_total_parts_for_program(
                                    machine["machine_id"],
                                    int(machine["program"]),
                                )
                                st.metric("Total Parts Produced", int(tp))
                            except (ValueError, TypeError):
                                st.metric("Total Parts Produced", "—")
                        else:
                            st.metric("Total Parts Produced", "—")
                    st.caption(f"🔧 {machine['spindle']:.0f} RPM · feed {machine['feed']:.0f}")
                    st.caption(f"🕐 Last poll (IST): {machine['last_update']}")
                    st.markdown("</div>", unsafe_allow_html=True)

                    exp_label = f"Alerts ({len(alerts)})" if alerts else "Alerts (0)"
                    with st.expander(exp_label, expanded=False):
                        if alerts:
                            for event in alerts[:5]:
                                render_alert_row(event)
                            if len(alerts) > 5:
                                with st.expander(
                                    f"Older ({len(alerts) - 5} more)",
                                    expanded=False,
                                ):
                                    for event in alerts[5:]:
                                        render_alert_row(event)
                        else:
                            st.caption("No alerts yet")
            st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.warning("⚠️ No data available. Make sure the CNC monitor is running.")

    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: gray; font-size: 12px;'>"
        "CNC Monitor Dashboard | Powered by Streamlit & Supabase"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
