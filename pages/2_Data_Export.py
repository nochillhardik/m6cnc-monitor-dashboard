import os
import sys
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.db_setup import get_connection
from display_format import format_ist_datetime


def get_machine_names():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT machine_name
        FROM machine_status
        WHERE machine_name IS NOT NULL
        ORDER BY machine_name
        """
    )
    names = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return names


def fetch_machine_status(start_dt, end_dt, machine_names):
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT
            timestamp,
            machine_name,
            status,
            mode,
            program_number,
            program_comment,
            part_count,
            feed_rate,
            spindle_speed
        FROM machine_status
        WHERE timestamp >= %s AND timestamp < %s
    """
    params = [start_dt, end_dt]

    if machine_names:
        query += " AND machine_name = ANY(%s)"
        params.append(machine_names)

    query += " ORDER BY timestamp DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame(
        rows,
        columns=[
            "_ts_raw",
            "Machine",
            "Status",
            "Mode",
            "Program #",
            "Program Name",
            "Part Count",
            "Feed Rate",
            "Spindle Speed",
        ],
    )
    if not df.empty:
        df["Timestamp (IST)"] = df["_ts_raw"].apply(
            lambda x: format_ist_datetime(x, include_date=True) if x else "-"
        )
        df = df.drop(columns=["_ts_raw"])
        cols = list(df.columns)
        cols.insert(0, cols.pop(cols.index("Timestamp (IST)")))
        df = df[cols]
    return df


def fetch_alarms(start_dt, end_dt, machine_names):
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT
            timestamp,
            machine_name,
            alarm_code,
            alarm_message,
            resolved
        FROM alarms
        WHERE timestamp >= %s AND timestamp < %s
    """
    params = [start_dt, end_dt]

    if machine_names:
        query += " AND machine_name = ANY(%s)"
        params.append(machine_names)

    query += " ORDER BY timestamp DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame(
        rows,
        columns=[
            "_ts_raw",
            "Machine",
            "Alert Code",
            "Alert Message",
            "Resolved",
        ],
    )
    if not df.empty:
        df["Timestamp (IST)"] = df["_ts_raw"].apply(
            lambda x: format_ist_datetime(x, include_date=True) if x else "-"
        )
        df = df.drop(columns=["_ts_raw"])
        df["Resolved"] = df["Resolved"].apply(lambda x: "Yes" if int(x) == 1 else "No")
        cols = list(df.columns)
        cols.insert(0, cols.pop(cols.index("Timestamp (IST)")))
        df = df[cols]
    return df


def fetch_production_tracking(start_dt, end_dt, machine_names):
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT
            machine_name,
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
        WHERE COALESCE(end_time, start_time) >= %s
          AND COALESCE(end_time, start_time) < %s
    """
    params = [start_dt, end_dt]

    if machine_names:
        query += " AND machine_name = ANY(%s)"
        params.append(machine_names)

    query += " ORDER BY COALESCE(end_time, start_time) DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame(
        rows,
        columns=[
            "Machine",
            "Program #",
            "Program Name",
            "_start_raw",
            "_end_raw",
            "Start Parts",
            "End Parts",
            "Parts Produced",
            "Duration (sec)",
            "Event Type",
        ],
    )
    if not df.empty:
        df["Start Time (IST)"] = df["_start_raw"].apply(
            lambda x: format_ist_datetime(x, include_date=True) if x else "-"
        )
        df["End Time (IST)"] = df["_end_raw"].apply(
            lambda x: format_ist_datetime(x, include_date=True) if x else "-"
        )
        df = df.drop(columns=["_start_raw", "_end_raw"])
        desired = [
            "Machine",
            "Program #",
            "Program Name",
            "Start Time (IST)",
            "End Time (IST)",
            "Start Parts",
            "End Parts",
            "Parts Produced",
            "Duration (sec)",
            "Event Type",
        ]
        df = df[[c for c in desired if c in df.columns]]
    return df


def dataframe_download(st_obj, df, filename_prefix):
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st_obj.download_button(
        label=f"Download CSV ({filename_prefix})",
        data=csv_bytes,
        file_name=f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True,
    )


def main():
    st.set_page_config(layout="wide", initial_sidebar_state="expanded", page_title="Data Export")
    st.title("Data Export")
    st.markdown("Export machine data to CSV for Excel analysis.")

    machine_names = get_machine_names()

    col1, col2 = st.columns(2)
    with col1:
        default_from = date.today() - timedelta(days=7)
        from_date = st.date_input("From Date", value=default_from)
    with col2:
        to_date = st.date_input("To Date", value=date.today())

    selected_machines = st.multiselect(
        "Machines (leave blank for all)",
        options=machine_names,
        default=[],
    )

    if to_date < from_date:
        st.error("To Date cannot be before From Date.")
        return

    start_dt = datetime.combine(from_date, datetime.min.time())
    end_dt = datetime.combine(to_date + timedelta(days=1), datetime.min.time())

    st.caption("Date filter is inclusive of From Date and To Date.")

    if st.button("Load Data", type="primary", use_container_width=True):
        with st.spinner("Loading data..."):
            status_df = fetch_machine_status(start_dt, end_dt, selected_machines)
            alarms_df = fetch_alarms(start_dt, end_dt, selected_machines)
            prod_df = fetch_production_tracking(start_dt, end_dt, selected_machines)

        st.subheader("1) Machine Status (raw polling timeline)")
        if status_df.empty:
            st.info("No machine status rows for selected filters.")
        else:
            st.dataframe(status_df, use_container_width=True)
            dataframe_download(st, status_df, "machine_status")

        st.subheader("2) Alerts / Alarms")
        if alarms_df.empty:
            st.info("No alert rows for selected filters.")
        else:
            st.dataframe(alarms_df, use_container_width=True)
            dataframe_download(st, alarms_df, "alerts")

        st.subheader("3) Production Tracking")
        if prod_df.empty:
            st.info("No production tracking rows for selected filters.")
        else:
            st.dataframe(prod_df, use_container_width=True)
            dataframe_download(st, prod_df, "production_tracking")


if __name__ == "__main__":
    main()
