import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.db_setup import get_connection
from display_format import format_ist_datetime


def get_distinct_machine_names():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT machine_name
            FROM production_tracking
            WHERE machine_name IS NOT NULL
            ORDER BY machine_name
            """
        )
        rows = [r[0] for r in cursor.fetchall()]
        cursor.close()
        conn.close()
        return rows
    except Exception:
        return []


def get_production_log_filtered(
    machine_names,
    program_number_str,
    program_name_substr,
    date_from,
    date_to,
):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = """
            SELECT
                machine_name,
                program_number,
                program_comment,
                start_time,
                end_time,
                parts_produced
            FROM production_tracking
            WHERE status = 'completed'
        """
        params = []

        if machine_names:
            query += " AND machine_name = ANY(%s)"
            params.append(machine_names)

        prog_num = None
        if program_number_str and str(program_number_str).strip():
            try:
                prog_num = int(str(program_number_str).strip())
            except ValueError:
                prog_num = None
            if prog_num is not None:
                query += " AND program_number = %s"
                params.append(prog_num)

        if program_name_substr and str(program_name_substr).strip():
            query += " AND program_comment ILIKE %s"
            params.append("%" + str(program_name_substr).strip() + "%")

        if date_from is not None:
            query += " AND COALESCE(end_time, start_time) >= %s"
            params.append(datetime.combine(date_from, datetime.min.time()))
        if date_to is not None:
            query += " AND COALESCE(end_time, start_time) < %s"
            params.append(datetime.combine(date_to + timedelta(days=1), datetime.min.time()))

        query += " ORDER BY end_time DESC NULLS LAST"

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
                "Start Time (IST)",
                "End Time (IST)",
                "Parts Produced",
            ],
        )

        if df.empty:
            return df

        df["Start Time (IST)"] = df["Start Time (IST)"].apply(
            lambda x: format_ist_datetime(x, include_date=True) if x else "-"
        )
        df["End Time (IST)"] = df["End Time (IST)"].apply(
            lambda x: format_ist_datetime(x, include_date=True) if x else "-"
        )
        df["Program Name"] = df["Program Name"].fillna("-")
        df["Parts Produced"] = df["Parts Produced"].fillna(0).astype(int)

        return df
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame(
            columns=[
                "Machine",
                "Program #",
                "Program Name",
                "Start Time (IST)",
                "End Time (IST)",
                "Parts Produced",
            ]
        )


def main():
    st.set_page_config(layout="wide", initial_sidebar_state="expanded", page_title="Production Logs")
    st.title("Production Logs")
    st.markdown("Search completed program segments by machine, program #, name, or date.")

    all_names = get_distinct_machine_names()

    col_a, col_b = st.columns(2)
    with col_a:
        sel = st.multiselect(
            "Machine",
            options=all_names,
            default=[],
            help="Leave empty for all machines.",
        )
    with col_b:
        prog_num = st.text_input("Program #", "", help="Exact program number.")

    name_q = st.text_input(
        "Program name contains",
        "",
        help="Matches program comment / name (partial, case-insensitive).",
    )
    st.caption("Date filter uses segment end time (or start if end missing).")

    col_f, col_g = st.columns(2)
    default_from = date.today() - timedelta(days=30)
    with col_f:
        date_from = st.date_input("From date", value=default_from, min_value=date(2000, 1, 1))
    with col_g:
        date_to = st.date_input("To date", value=date.today(), min_value=date(2000, 1, 1))

    if date_to < date_from:
        st.error("To date cannot be before from date.")
        return

    machine_filter = sel if sel else None

    df = get_production_log_filtered(
        machine_names=machine_filter,
        program_number_str=prog_num,
        program_name_substr=name_q,
        date_from=date_from,
        date_to=date_to,
    )

    if df.empty:
        st.warning("No rows match your filters.")
    else:
        st.success(f"{len(df)} row(s) found.")
        st.dataframe(df, use_container_width=True)


if __name__ == "__main__":
    main()
