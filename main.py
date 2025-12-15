import streamlit as st
import pandas as pd
import mysql.connector
import folium
from streamlit_folium import st_folium

import datetime as dt

ALLOWED_TABLES = ["buildings", "lots", "lot_permit", "lot_inventory"]

def get_table_schema(table_name: str) -> pd.DataFrame:
    """Returns column schema for a table from INFORMATION_SCHEMA."""
    sql = """
    SELECT 
        COLUMN_NAME,
        DATA_TYPE,
        IS_NULLABLE,
        COLUMN_KEY,
        EXTRA
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = %(t)s
    ORDER BY ORDINAL_POSITION;
    """
    return fetch_df(sql, {"t": table_name})

def get_primary_keys(schema_df: pd.DataFrame) -> list[str]:
    return schema_df.loc[schema_df["COLUMN_KEY"] == "PRI", "COLUMN_NAME"].tolist()

def coerce_input(data_type: str, value):
    """Convert form inputs to Python types that mysql.connector will handle well."""
    if value is None:
        return None
    dtp = data_type.lower()

    if dtp in ("int", "bigint", "smallint", "mediumint", "tinyint"):
        return int(value)
    if dtp in ("decimal", "numeric", "float", "double"):
        return float(value)
    if dtp in ("date",):
        if isinstance(value, dt.date):
            return value
        return dt.date.fromisoformat(str(value))
    if dtp in ("datetime", "timestamp"):
        # Streamlit returns datetime for st.date_input+time_input combos if you build it
        if isinstance(value, dt.datetime):
            return value
        return dt.datetime.fromisoformat(str(value))

    # default treat as string
    return str(value)

def render_input(col_name: str, data_type: str, is_nullable: str):
    """Build a Streamlit input widget based on MySQL data type."""
    dtp = data_type.lower()
    required = (is_nullable == "NO")

    if dtp in ("int", "bigint", "smallint", "mediumint", "tinyint"):
        return st.number_input(col_name, value=None, step=1, format="%d")
    if dtp in ("decimal", "numeric", "float", "double"):
        return st.number_input(col_name, value=None)

    if dtp == "date":
        return st.date_input(col_name, value=None)

    if dtp in ("datetime", "timestamp"):
        # simple text input is easiest unless you want separate date+time
        return st.text_input(col_name, value="")

    # varchar/text/etc
    default = "" if required else ""
    return st.text_input(col_name, value=default)

def run_sql_many(sql: str, data: list[tuple]):
    conn = get_conn()
    cur = conn.cursor()
    cur.executemany(sql, data)
    conn.commit()
    cur.close()
    conn.close()



DB = dict(user="root", password="bCcgjUHUUMWBxhENRriWfeYjUYswzcTi", host="yamabiko.proxy.rlwy.net", port=57345, database="adt_project")


def get_conn():
    return mysql.connector.connect(**DB)

def fetch_df(sql, params=None):
    conn = get_conn()
    df = pd.read_sql(sql, conn, params=params)
    conn.close()
    return df

def run_sql(sql, params=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params or {})
    conn.commit()
    cur.close()
    conn.close()


def safe_rerun():
    """Trigger a Streamlit rerun in a way that works across Streamlit versions."""
    try:
        # older/newer Streamlit versions may provide different helpers
        st.experimental_rerun()
        return
    except Exception:
        pass

    try:
        # fallback to internal RerunException
        from streamlit.runtime.scriptrunner.script_runner import RerunException

        raise RerunException()
    except Exception:
        # final fallback: ask user to refresh
        st.warning("Please refresh the app to continue.")

st.set_page_config(page_title="SmartPark IU", layout="wide")

page = st.sidebar.radio("Navigate", ["Park Now", "Admin"])

# simple session state for admin authentication
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False
if page == "Park Now":
    st.title("Where should I park right now?")

    # --- load reference tables ---
    buildings = fetch_df("SELECT building_id, name, latitude, longitude FROM buildings ORDER BY name")
    permits = fetch_df("SELECT permit_id, name FROM permits ORDER BY name")

    if buildings.empty:
        st.error("No buildings found in database.")
        st.stop()

    # --- session state (so map reruns don't wipe results) ---
    if "recs" not in st.session_state:
        st.session_state.recs = None
    if "building_center" not in st.session_state:
        st.session_state.building_center = None
    if "submitted_once" not in st.session_state:
        st.session_state.submitted_once = False

    # --- UI in a form to prevent constant reruns ---
    with st.form("park_form"):
        b_choice = st.selectbox("Destination Building", buildings["name"].tolist())

        permit_options = ["Any"] + (permits["name"].tolist() if not permits.empty else [])
        p_choice = st.selectbox("Permit Type", permit_options)

        max_walk_min = st.slider("Max walk (minutes)", 1, 30, 10)
        k = st.slider("Top results", 3, 20, 10)

        submitted = st.form_submit_button("Find parking")

        # Small scrollable preview of the `lots` table under the first block
        try:
            lots_preview = fetch_df("SELECT lot_id, title, latitude, longitude FROM lots ORDER BY title LIMIT 200")
        except Exception:
            lots_preview = pd.DataFrame()

        st.caption("Lots preview ")
        st.dataframe(lots_preview, height=200)
    b_row = buildings[buildings["name"] == b_choice].iloc[0]

    # --- SQL: Any permit (no filtering) ---
    REC_SQL_ANY = """
    SELECT
      l.lot_id,
      l.title AS lot_title,
      l.latitude AS lot_lat,
      l.longitude AS lot_lng,
      d.distance,
      li.capacity_total,
      li.snapshot_ts,
      GROUP_CONCAT(DISTINCT p.name ORDER BY p.name SEPARATOR ', ') AS parking_types
    FROM lot_building_distance d
    JOIN lots l ON l.lot_id = d.lot_id
    LEFT JOIN lot_permit lp ON lp.lot_id = l.lot_id
    LEFT JOIN permits p ON p.permit_id = lp.permit_id
    JOIN (
      SELECT lot_id, MAX(snapshot_ts) AS max_ts
      FROM lot_inventory
      GROUP BY lot_id
    ) latest ON latest.lot_id = l.lot_id
    JOIN lot_inventory li ON li.lot_id = latest.lot_id AND li.snapshot_ts = latest.max_ts
    WHERE d.building_id = %(building_id)s
      AND d.distance <= %(max_walk_min)s * 60
    GROUP BY l.lot_id, l.title, l.latitude, l.longitude, d.distance, li.capacity_total, li.snapshot_ts
    ORDER BY d.distance ASC, li.capacity_total DESC
    LIMIT %(k)s;
    """

    # --- SQL: specific permit filter, but still show all types via LEFT JOIN ---
    REC_SQL_PERMIT = """
    SELECT
      l.lot_id,
      l.title AS lot_title,
      l.latitude AS lot_lat,
      l.longitude AS lot_lng,
      d.distance,
      li.capacity_total,
      li.snapshot_ts,
      GROUP_CONCAT(DISTINCT p.name ORDER BY p.name SEPARATOR ', ') AS parking_types
    FROM lot_building_distance d
    JOIN lots l ON l.lot_id = d.lot_id
    LEFT JOIN lot_permit lp ON lp.lot_id = l.lot_id
    LEFT JOIN permits p ON p.permit_id = lp.permit_id
    JOIN (
      SELECT lot_id, MAX(snapshot_ts) AS max_ts
      FROM lot_inventory
      GROUP BY lot_id
    ) latest ON latest.lot_id = l.lot_id
    JOIN lot_inventory li ON li.lot_id = latest.lot_id AND li.snapshot_ts = latest.max_ts
    WHERE d.building_id = %(building_id)s
      AND d.distance <= %(max_walk_min)s * 60
      AND EXISTS (
        SELECT 1 FROM lot_permit lp2
        WHERE lp2.lot_id = l.lot_id AND lp2.permit_id = %(permit_id)s
      )
    GROUP BY l.lot_id, l.title, l.latitude, l.longitude, d.distance, li.capacity_total, li.snapshot_ts
    ORDER BY d.distance ASC, li.capacity_total DESC
    LIMIT %(k)s;
    """

    if submitted:
        if p_choice == "Any":
            rec_sql = REC_SQL_ANY
            params = {
                "building_id": int(b_row["building_id"]),
                "max_walk_min": int(max_walk_min),
                "k": int(k),
            }
        else:
            if permits.empty:
                st.error("Permits table is empty, can't filter by permit.")
                st.stop()

            p_row = permits[permits["name"] == p_choice].iloc[0]
            rec_sql = REC_SQL_PERMIT
            params = {
                "building_id": int(b_row["building_id"]),
                "permit_id": int(p_row["permit_id"]),
                "max_walk_min": int(max_walk_min),
                "k": int(k),
            }

        recs = fetch_df(rec_sql, params)

        st.session_state.recs = recs
        st.session_state.building_center = (float(b_row["latitude"]), float(b_row["longitude"]), b_choice)
        st.session_state.submitted_once = True

    # --- Render results OUTSIDE submit (so map reruns don't wipe UI) ---
    if st.session_state.submitted_once:
        recs = st.session_state.recs

        if recs is None or recs.empty:
            st.warning("No lots found within the selected walking time.")
        else:
            show = recs.copy()
            show["walk_min"] = (show["distance"] / 60).round(1)
            show["parking_types"] = show["parking_types"].fillna("")

            st.dataframe(
                show[["lot_title", "parking_types", "walk_min", "capacity_total", "snapshot_ts"]],
                use_container_width=True
            )

            st.subheader("Map")
            lat0, lng0, bname = st.session_state.building_center
            m = folium.Map(location=[lat0, lng0], zoom_start=15)

            folium.Marker(
                [lat0, lng0],
                popup=f"Destination: {bname}",
                tooltip="Destination"
            ).add_to(m)

            # ensure lat/lng are valid
            recs2 = recs.dropna(subset=["lot_lat", "lot_lng"]).copy()
            recs2["lot_lat"] = recs2["lot_lat"].astype(float)
            recs2["lot_lng"] = recs2["lot_lng"].astype(float)
            recs2["parking_types"] = recs2["parking_types"].fillna("")

            for _, r in recs2.iterrows():
                popup = (
                    f"<b>{r['lot_title']}</b><br>"
                    f"Types: {r['parking_types']}<br>"
                    f"Walk: {round(r['distance']/60,1)} min<br>"
                    f"Capacity: {r['capacity_total']}<br>"
                    f"Snapshot: {r['snapshot_ts']}"
                )
                folium.CircleMarker(
                    location=[r["lot_lat"], r["lot_lng"]],
                    radius=8,
                    popup=popup,
                    tooltip=r["lot_title"],
                ).add_to(m)

            # IMPORTANT: prevent interaction return objects from causing flicker issues
            st_folium(m, width=1100, height=600, returned_objects=[], key="park_map")

elif page == "Admin":
    # If not authenticated, show a dummy login form (blank-check only)
    if not st.session_state.admin_authenticated:
        st.title("Admin Login")
        with st.form("admin_login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")

        if submitted:
            if not username or not password:
                st.error("Username and password cannot be blank.")
            else:
                st.session_state.admin_authenticated = True
                st.success("Logged in successfully.")

        # If still not authenticated (form not submitted or blank inputs), halt here
        if not st.session_state.admin_authenticated:
            st.stop()

    # Authenticated — show admin portal
    st.title("Admin")
    if st.button("Logout"):
        st.session_state.admin_authenticated = False
        safe_rerun()

    tab1, tab2, tab3 = st.tabs(["Manage Lots/Buildings","Upload Distances CSV", "Materialize Distances"])

    with tab2:
        st.write("Upload CSV for staging_lot_building_distance (columns must match your staging schema).")
        f = st.file_uploader("Upload CSV", type=["csv"])
        if f is not None:
            df = pd.read_csv(f)
            st.write("Preview:", df.head())

            if st.button("Load into staging (truncate + insert)"):
                run_sql("TRUNCATE TABLE staging_lot_building_distance;")

                conn = get_conn()
                cur = conn.cursor()
                cols = df.columns.tolist()
                placeholders = ",".join(["%s"] * len(cols))
                colnames = ",".join(cols)

                sql = f"INSERT INTO staging_lot_building_distance ({colnames}) VALUES ({placeholders})"
                data = [tuple(x) for x in df.itertuples(index=False, name=None)]

                chunk = 5000
                for i in range(0, len(data), chunk):
                    cur.executemany(sql, data[i:i+chunk])
                    conn.commit()

                cur.close()
                conn.close()
                st.success(f"Loaded {len(df)} rows into staging.")

    with tab3:
        st.write("Upsert from staging into lot_building_distance.")
        if st.button("Run upsert"):
            upsert_sql = """
            INSERT INTO lot_building_distance (lot_id, building_id, distance)
            SELECT l.lot_id, b.building_id, CAST(s.distance_sec_raw AS UNSIGNED)
            FROM staging_lot_building_distance s
            JOIN lots l ON LOWER(TRIM(l.title)) = LOWER(TRIM(s.lot_title_raw))
            JOIN buildings b ON LOWER(TRIM(b.name)) = LOWER(TRIM(s.building_name_raw))
            ON DUPLICATE KEY UPDATE distance = VALUES(distance);
            """
            run_sql(upsert_sql)
            st.success("Upsert completed.")

    with tab1:
        st.subheader("CRUD Portal")

        table = st.selectbox("Select table", ALLOWED_TABLES)
        action = st.selectbox("Action", ["Insert", "Update", "Delete"])

        schema = get_table_schema(table)
        pk_cols = get_primary_keys(schema)

        if schema.empty:
            st.error("Could not load schema for this table.")
            st.stop()

        st.caption(f"Primary key columns: {pk_cols if pk_cols else 'None detected'}")

        # Pull a small preview to help admin choose rows for update/delete
        preview = fetch_df(f"SELECT * FROM {table} LIMIT 200")
        whole_data = fetch_df(f"SELECT * FROM {table} LIMIT 10000") 
        st.write("Preview (first 200 rows):")
        st.dataframe(preview, use_container_width=True, height=250)

        # For Update/Delete, we need to pick a row (by PK if possible)
        selected_pk = {}
        if action in ("Update", "Delete"):
            if not pk_cols:
                st.warning("No primary key found. Update/Delete will be limited.")
            else:
                st.write("Select row to modify:")
                for pk in pk_cols:
                    # pick from existing values in preview if present
                    if pk in whole_data.columns and not whole_data.empty:
                        options = whole_data[pk].dropna().unique().tolist()
                        selected_pk[pk] = st.selectbox(f"PK: {pk}", options)
                    else:
                        selected_pk[pk] = st.text_input(f"PK: {pk}")

        # Insert / Update form
        with st.form(f"{table}_{action}_form", clear_on_submit=False):
            inputs = {}

            if action == "Insert":
                st.write("Enter values to insert:")
                for _, row in schema.iterrows():
                    col = row["COLUMN_NAME"]
                    # Skip auto-increment columns on insert
                    if str(row["EXTRA"]).lower().find("auto_increment") >= 0:
                        continue
                    inputs[col] = render_input(col, row["DATA_TYPE"], row["IS_NULLABLE"])

            elif action == "Update":
                st.write("Enter new values (leave blank to keep unchanged):")
                for _, row in schema.iterrows():
                    col = row["COLUMN_NAME"]
                    if col in pk_cols:
                        continue  # don't update PK
                    # allow user to leave blank = no change
                    inputs[col] = st.text_input(f"{col} (new value or blank)", value="")

            elif action == "Delete":
                st.write("You are about to delete the selected row.")
                st.warning("This cannot be undone.")

            submitted = st.form_submit_button(f"{action} row")

        # Execute
        if submitted:
            try:
                if action == "Insert":
                    cols = list(inputs.keys())
                    placeholders = ", ".join(["%s"] * len(cols))
                    colnames = ", ".join(cols)

                    values = []
                    for c in cols:
                        meta = schema[schema["COLUMN_NAME"] == c].iloc[0]
                        v = inputs[c]
                        if isinstance(v, str) and v == "":
                            v = None
                        values.append(coerce_input(meta["DATA_TYPE"], v))

                    sql = f"INSERT INTO {table} ({colnames}) VALUES ({placeholders})"
                    run_sql(sql, tuple(values))
                    st.success("Inserted successfully.")
                    safe_rerun()

                elif action == "Update":
                    if not pk_cols:
                        st.error("Update requires a primary key.")
                    else:
                        set_parts = []
                        values = []

                        for col, raw in inputs.items():
                            # blank = do not update
                            if raw is None:
                                continue
                            if isinstance(raw, str) and raw.strip() == "":
                                continue

                            meta = schema[schema["COLUMN_NAME"] == col].iloc[0]
                            set_parts.append(f"{col}=%s")
                            values.append(coerce_input(meta["DATA_TYPE"], raw))

                        if not set_parts:
                            st.warning("No fields provided to update.")
                        else:
                            where_parts = []
                            for pk in pk_cols:
                                where_parts.append(f"{pk}=%s")
                                pk_meta = schema[schema["COLUMN_NAME"] == pk].iloc[0]
                                values.append(coerce_input(pk_meta["DATA_TYPE"], selected_pk[pk]))

                            sql = f"UPDATE {table} SET {', '.join(set_parts)} WHERE {' AND '.join(where_parts)}"
                            run_sql(sql, tuple(values))
                            st.success("Updated successfully.")
                            safe_rerun()

                elif action == "Delete":
                    if not pk_cols:
                        st.error("Delete requires a primary key.")
                    else:
                        where_parts = []
                        values = []
                        for pk in pk_cols:
                            where_parts.append(f"{pk}=%s")
                            pk_meta = schema[schema["COLUMN_NAME"] == pk].iloc[0]
                            values.append(coerce_input(pk_meta["DATA_TYPE"], selected_pk[pk]))

                        sql = f"DELETE FROM {table} WHERE {' AND '.join(where_parts)}"
                        run_sql(sql, tuple(values))
                        st.success("Deleted successfully.")
                        safe_rerun()

            except Exception as e:
                st.error(f"Operation failed: {e}")

