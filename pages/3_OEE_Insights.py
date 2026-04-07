import os
import sys
from datetime import date, datetime, timedelta, timezone

import altair as alt
import pandas as pd
import streamlit as st

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.db_setup import get_connection
from display_format import format_ist_datetime
from config import (
    DOWNTIME_MIN_THRESHOLD,
    SANDWICH_BIN_MINUTES,
    SANDWICH_DOWNTIME_SPINDLE_THRESHOLD,
    SANDWICH_MEM_MODE_VALUES,
    SANDWICH_MIN_STATE_DURATION_MINUTES,
)

IST = timezone(timedelta(hours=5, minutes=30))


def to_ist(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)


def get_machine_names():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT machine_name
        FROM (
            SELECT machine_name FROM machine_status WHERE machine_name IS NOT NULL
            UNION
            SELECT machine_name FROM production_tracking WHERE machine_name IS NOT NULL
        ) u
        ORDER BY machine_name
        """
    )
    machines = [r[0] for r in cursor.fetchall()]
    cursor.close()
    conn.close()
    return machines


def get_status_rows(machine_name, start_dt, end_dt):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT timestamp, spindle_speed, mode, status
        FROM machine_status
        WHERE machine_name = %s
          AND timestamp >= %s
          AND timestamp < %s
        ORDER BY timestamp ASC
        """,
        (machine_name, start_dt, end_dt),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return pd.DataFrame(rows, columns=["timestamp", "spindle_speed", "mode", "status"])


def _smooth_short_runs(states, min_len):
    if min_len <= 1 or not states:
        return states
    out = states[:]
    i = 0
    n = len(out)
    while i < n:
        j = i + 1
        while j < n and out[j] == out[i]:
            j += 1
        if (j - i) < min_len and i > 0:
            for k in range(i, j):
                out[k] = out[i - 1]
        i = j
    return out


def compute_sandwich_timeline(status_df, start_dt, end_dt):
    cols = ["minute", "state", "downtime", "mem_running", "other_mode", "offline"]
    if start_dt >= end_dt:
        return pd.DataFrame(columns=cols)

    minute_index = pd.date_range(
        start=start_dt,
        end=end_dt - timedelta(minutes=SANDWICH_BIN_MINUTES),
        freq=f"{SANDWICH_BIN_MINUTES}min",
    )
    if len(minute_index) == 0:
        return pd.DataFrame(columns=cols)

    base = pd.DataFrame({"minute": minute_index})
    if status_df.empty:
        base["state"] = "offline"
    else:
        tmp = status_df.copy()
        tmp["timestamp"] = pd.to_datetime(tmp["timestamp"], errors="coerce")
        tmp = tmp.dropna(subset=["timestamp"])
        if tmp.empty:
            base["state"] = "offline"
        else:
            tmp["minute"] = tmp["timestamp"].dt.floor(f"{SANDWICH_BIN_MINUTES}min")
            # Use last poll in each minute as representative state.
            snap = tmp.groupby("minute", as_index=False).last()
            merged = base.merge(
                snap[["minute", "spindle_speed", "mode", "status"]],
                on="minute",
                how="left",
            )

            def classify(row):
                mode = (str(row.get("mode") or "")).strip().upper()
                status = (str(row.get("status") or "")).strip().lower()
                spindle = row.get("spindle_speed")

                if spindle is not None and pd.notna(spindle):
                    if float(spindle) <= SANDWICH_DOWNTIME_SPINDLE_THRESHOLD:
                        return "downtime"  # red
                    if mode in SANDWICH_MEM_MODE_VALUES:
                        return "mem_running"  # green
                    if mode:
                        return "other_mode"  # blue
                    if status and status != "offline":
                        return "other_mode"  # blue
                return "offline"  # gray

            states = merged.apply(classify, axis=1).tolist()
            if SANDWICH_MIN_STATE_DURATION_MINUTES > 1:
                states = _smooth_short_runs(states, SANDWICH_MIN_STATE_DURATION_MINUTES)
            base["state"] = states

    for name in ["downtime", "mem_running", "other_mode", "offline"]:
        base[name] = (base["state"] == name).astype(int)
    return base[cols]


def render_sandwich_chart(timeline_df):
    if timeline_df.empty:
        st.info("No status data to build sandwich timeline for this range.")
        return

    vis = timeline_df.copy()
    vis["state_label"] = vis["state"].map(
        {
            "downtime": "Downtime",
            "mem_running": "Running (MEM)",
            "other_mode": "Other Mode",
            "offline": "Offline/No Data",
        }
    )
    vis["minute_label"] = vis["minute"].apply(
        lambda x: format_ist_datetime(
            x.to_pydatetime() if hasattr(x, "to_pydatetime") else x,
            include_date=True,
        )
    )
    vis["row"] = "Timeline"
    color_scale = alt.Scale(
        domain=["Downtime", "Running (MEM)", "Other Mode", "Offline/No Data"],
        range=["#e53935", "#43a047", "#1e88e5", "#9e9e9e"],
    )
    chart = (
        alt.Chart(vis)
        .mark_rect()
        .encode(
            x=alt.X("minute:T", title=None),
            y=alt.Y("row:N", title=None),
            color=alt.Color("state_label:N", scale=color_scale, legend=alt.Legend(title=None)),
            tooltip=[
                alt.Tooltip("minute_label:N", title="Time (IST)"),
                alt.Tooltip("state_label:N", title="State"),
            ],
        )
        .properties(height=60)
    )
    st.altair_chart(chart, use_container_width=True)

    total = len(vis)
    counts = vis["state"].value_counts()
    mins = {
        "red": int(counts.get("downtime", 0)),
        "green": int(counts.get("mem_running", 0)),
        "blue": int(counts.get("other_mode", 0)),
        "gray": int(counts.get("offline", 0)),
    }
    p = {k: (v * 100.0 / total if total else 0.0) for k, v in mins.items()}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Red (Downtime)", f"{mins['red']} min", f"{p['red']:.1f}%")
    c2.metric("Green (MEM running)", f"{mins['green']} min", f"{p['green']:.1f}%")
    c3.metric("Blue (Other mode)", f"{mins['blue']} min", f"{p['blue']:.1f}%")
    c4.metric("Gray (Offline)", f"{mins['gray']} min", f"{p['gray']:.1f}%")


def get_production_rows(machine_name, start_dt, end_dt):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COALESCE(end_time, start_time) AS event_time, parts_produced
        FROM production_tracking
        WHERE machine_name = %s
          AND COALESCE(end_time, start_time) >= %s
          AND COALESCE(end_time, start_time) < %s
        ORDER BY event_time ASC
        """,
        (machine_name, start_dt, end_dt),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return pd.DataFrame(rows, columns=["event_time", "parts_produced"])


def compute_downtime_episodes(status_df, window_end):
    """
    Downtime episode rule:
    spindle_speed == 0 continuously for more than 15 minutes.
    Entire duration is counted once threshold is crossed.
    """
    if status_df.empty:
        return pd.DataFrame(columns=["start_time", "end_time", "minutes"])

    status_df = status_df.copy()
    status_df["spindle_speed"] = status_df["spindle_speed"].fillna(0)
    status_df["is_down"] = status_df["spindle_speed"] == 0

    episodes = []
    down_start = None

    for _, row in status_df.iterrows():
        ts = row["timestamp"]
        is_down = bool(row["is_down"])

        if is_down and down_start is None:
            down_start = ts
        elif not is_down and down_start is not None:
            mins = (ts - down_start).total_seconds() / 60.0
            if mins > DOWNTIME_MIN_THRESHOLD:
                episodes.append({"start_time": down_start, "end_time": ts, "minutes": mins})
            down_start = None

    if down_start is not None:
        mins = (window_end - down_start).total_seconds() / 60.0
        if mins > DOWNTIME_MIN_THRESHOLD:
            episodes.append({"start_time": down_start, "end_time": window_end, "minutes": mins})

    return pd.DataFrame(episodes, columns=["start_time", "end_time", "minutes"])


def compute_performance_hourly(prod_df):
    if prod_df.empty:
        return pd.DataFrame(columns=["hour", "parts"])

    tmp = prod_df.copy()
    tmp["parts_produced"] = tmp["parts_produced"].fillna(0).astype(int)
    tmp["event_time"] = pd.to_datetime(tmp["event_time"], utc=False, errors="coerce")
    tmp = tmp.dropna(subset=["event_time"])
    if tmp.empty:
        return pd.DataFrame(columns=["hour", "parts"])

    tmp["hour"] = tmp["event_time"].dt.floor("h")
    hourly = (
        tmp.groupby("hour", as_index=False)["parts_produced"]
        .sum()
        .rename(columns={"parts_produced": "parts"})
        .sort_values("hour")
    )
    return hourly


def main():
    st.set_page_config(layout="wide", initial_sidebar_state="expanded", page_title="OEE Insights")
    st.title("OEE Insights")
    st.markdown("Downtime and performance view. Filter by machine and date range.")

    machines = get_machine_names()
    if not machines:
        st.warning("No machine data found yet.")
        return

    fc1, fc2, fc3 = st.columns([1, 1, 2])
    with fc1:
        range_choice = st.selectbox(
            "Time range",
            ["Custom", "Last 24 hours", "Last 7 days"],
            index=1,
            help="Custom lets you pick From / To dates (inclusive).",
        )
    with fc2:
        selected_machines = st.multiselect(
            "Machines",
            options=machines,
            default=[],
            help="Leave empty to include all machines.",
        )
    with fc3:
        st.caption("Charts use data between window start and end (UTC-aligned dates, shown in IST).")

    start = None
    end = None
    if range_choice == "Custom":
        dc1, dc2 = st.columns(2)
        default_from = date.today() - timedelta(days=7)
        with dc1:
            from_date = st.date_input("From date", value=default_from)
        with dc2:
            to_date = st.date_input("To date", value=date.today())
        if to_date < from_date:
            st.error("To date cannot be before From date.")
            return
        start = datetime.combine(from_date, datetime.min.time())
        end = datetime.combine(to_date + timedelta(days=1), datetime.min.time())
    else:
        now = datetime.now(timezone.utc)
        end = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        if range_choice == "Last 24 hours":
            start = end - timedelta(hours=24)
        else:
            start = end - timedelta(days=7)

    # Normalise for DB comparisons (timestamps from Postgres are usually naive UTC)
    if start.tzinfo is not None:
        start = start.replace(tzinfo=None)
    if end.tzinfo is not None:
        end = end.replace(tzinfo=None)

    st.caption(
        f"Window: {format_ist_datetime(start.replace(tzinfo=timezone.utc), include_date=True)} → "
        f"{format_ist_datetime(end.replace(tzinfo=timezone.utc), include_date=True)} IST"
    )

    to_show = machines if not selected_machines else list(selected_machines)

    for machine_name in to_show:
        st.divider()
        st.subheader(machine_name)

        status_df = get_status_rows(machine_name, start, end)
        prod_df = get_production_rows(machine_name, start, end)

        timeline_df = compute_sandwich_timeline(status_df, start, end)
        st.caption(
            "Sandwich line rules: red = spindle <= 0, green = MEM with spindle > 0, "
            "blue = other active mode, gray = offline/no data."
        )
        render_sandwich_chart(timeline_df)

        downtime_df = compute_downtime_episodes(status_df, end)
        total_downtime_mins = float(downtime_df["minutes"].sum()) if not downtime_df.empty else 0.0

        perf_hourly_df = compute_performance_hourly(prod_df)
        total_parts = int(perf_hourly_df["parts"].sum()) if not perf_hourly_df.empty else 0

        c1, c2 = st.columns(2)
        with c1:
            st.metric("Total Downtime (min)", f"{total_downtime_mins:.1f}")
            st.markdown("**Downtime Episodes (spindle=0 for >15 min)**")
            if downtime_df.empty:
                st.info("No qualifying downtime episode in this range.")
            else:
                plot_df = downtime_df.copy()
                plot_df["episode"] = plot_df["start_time"].apply(
                    lambda x: format_ist_datetime(x, include_date=True)
                )
                plot_df = plot_df.set_index("episode")[["minutes"]]
                st.bar_chart(plot_df, use_container_width=True)
                details = downtime_df.copy()
                details["Start (IST)"] = details["start_time"].apply(
                    lambda x: format_ist_datetime(x, include_date=True)
                )
                details["End (IST)"] = details["end_time"].apply(
                    lambda x: format_ist_datetime(x, include_date=True)
                )
                details["Downtime (min)"] = details["minutes"].round(1)
                st.dataframe(details[["Start (IST)", "End (IST)", "Downtime (min)"]], use_container_width=True)

        with c2:
            st.metric("Total Parts Produced", total_parts)
            st.markdown("**Performance (Parts Produced per Hour)**")
            if perf_hourly_df.empty:
                st.info("No production records in this range.")
            else:
                plot_df = perf_hourly_df.copy()
                plot_df["hour_ist"] = plot_df["hour"].apply(
                    lambda x: format_ist_datetime(
                        x.to_pydatetime() if hasattr(x, "to_pydatetime") else x,
                        include_date=True,
                    )
                )
                plot_df = plot_df.set_index("hour_ist")[["parts"]]
                st.bar_chart(plot_df, use_container_width=True)

                by_day = perf_hourly_df.copy()
                by_day["day"] = by_day["hour"].apply(lambda x: to_ist(x).strftime("%A"))
                weekday_order = [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ]
                day_summary = (
                    by_day.groupby("day", as_index=False)["parts"]
                    .sum()
                    .set_index("day")
                    .reindex(weekday_order)
                    .fillna(0)
                )
                st.caption("Day-wise parts summary")
                st.bar_chart(day_summary, use_container_width=True)


if __name__ == "__main__":
    main()
