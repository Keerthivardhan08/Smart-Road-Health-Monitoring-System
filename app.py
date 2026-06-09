import streamlit as st
import pandas as pd
import sqlite3
import random
import math
import os
import smtplib

from datetime import datetime
from email.mime.text import MIMEText
from fpdf import FPDF

import folium
from folium.plugins import HeatMap

from streamlit_folium import st_folium
from ultralytics import YOLO
from PIL import Image
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

# ==================================================
# CONFIG
# ==================================================

st.set_page_config(
    page_title="Municipal Infrastructure AI",
    layout="wide"
)

os.makedirs("reports", exist_ok=True)

# Pulling from Streamlit Secrets securely
SENDER_EMAIL = st.secrets["EMAIL"]
APP_PASSWORD = st.secrets["PASS"]
AUTHORITY_EMAIL = "hypothalamus2108@gmail.com"

# ==================================================
# LOAD MODEL
# ==================================================

@st.cache_resource
def load_model():
    try:
        model = YOLO("finalv3.pt")
        return model

    except Exception as e:
        st.error(f"Model Error: {e}")
        return None

model = load_model()

# ==================================================
# DATABASE
# ==================================================

def init_db():

    conn = sqlite3.connect(
        "municipal_operationsv3.db",
        check_same_thread=False
    )

    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS tickets (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        ticket_id TEXT UNIQUE,

        email TEXT,

        date TEXT,

        lat REAL,
        lon REAL,

        zone TEXT,

        potholes INTEGER,
        transverse INTEGER,
        longitudinal INTEGER,
        alligator INTEGER,

        pci INTEGER,

        condition TEXT,
        priority TEXT,
        action TEXT,

        status TEXT,

        contractor TEXT,

        deadline TEXT,

        user_feedback TEXT

    )
    """)

    conn.commit()

    return conn, c


conn, c = init_db()

# ==================================================
# DUPLICATE DETECTION
# ==================================================

def is_duplicate(lat, lon):

    rows = c.execute("""
        SELECT ticket_id, lat, lon
        FROM tickets
        WHERE status != 'Resolved'
    """).fetchall()

    for row in rows:

        existing_ticket = row[0]
        old_lat = row[1]
        old_lon = row[2]

        distance = math.sqrt(
            (lat - old_lat) ** 2 +
            (lon - old_lon) ** 2
        ) * 111000

        if distance < 50:
            return True, existing_ticket

    return False, None

# ==================================================
# SEVERITY ENGINE
# ==================================================

def get_severity(confidence):

    if confidence >= 0.60:
        return "High"

    elif confidence >= 0.50:
        return "Medium"

    return "Low"

# ==================================================
# MAINTENANCE RECOMMENDATION ENGINE
# ==================================================

def recommend_maintenance(counts):

    if counts["alligator"] > 0:

        return (
            "Full Depth Reconstruction",
            "Priority 1",
            "Critical Structural Failure"
        )

    elif counts["potholes"] >= 3:

        return (
            "Full Depth Patching",
            "Priority 2",
            "Multiple Potholes Detected"
        )

    elif counts["potholes"] > 0:

        return (
            "Pothole Repair",
            "Priority 3",
            "Localized Damage"
        )

    elif counts["transverse"] > 2:

        return (
            "Crack Sealing",
            "Priority 4",
            "Thermal Cracking"
        )

    elif counts["longitudinal"] > 2:

        return (
            "Joint Sealing",
            "Priority 5",
            "Linear Cracking"
        )

    return (
        "Routine Monitoring",
        "Priority 6",
        "Road Condition Acceptable"
    )

# ==================================================
# ADVANCED PCI ENGINE
# ==================================================

def calculate_engineering_metrics(counts):

    pci = 100 - (
        counts['longitudinal'] * 5 +
        counts['transverse'] * 8 +
        counts['potholes'] * 18 +
        counts['alligator'] * 30
    )

    pci = max(0, pci)

    if pci >= 85:
        condition = "Excellent"

    elif pci >= 70:
        condition = "Good"

    elif pci >= 55:
        condition = "Fair"

    elif pci >= 40:
        condition = "Poor"

    elif pci >= 20:
        condition = "Very Poor"

    else:
        condition = "Failed"

    dispatch_required = "No"

    # =========================
    # OVERRIDE RULES
    # =========================

    if counts["alligator"] >= 1:

        priority = "Critical"

        action = (
            "Immediate Structural Rehabilitation Required"
        )

        dispatch_required = "Yes"

    elif counts["potholes"] >= 1:

        priority = "High"

        action = (
            "Immediate Pothole Repair Required"
        )

        dispatch_required = "Yes"

    else:

        if pci < 40:

            priority = "High"

            action = "Major Rehabilitation Required"

        elif pci < 60:

            priority = "Medium"

            action = "Preventive Maintenance Required"

        else:

            priority = "Low"

            action = "Routine Monitoring"

    return (
        pci,
        condition,
        priority,
        action,
        dispatch_required
    )
# ==================================================
# EMAIL SYSTEM
# ==================================================

def send_email(to_email, subject, body):

    if not to_email:
        return

    try:

        server = smtplib.SMTP(
            "smtp.gmail.com",
            587
        )

        server.starttls()

        server.login(
            SENDER_EMAIL,
            APP_PASSWORD
        )

        msg = MIMEText(body)

        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email

        server.sendmail(
            SENDER_EMAIL,
            to_email,
            msg.as_string()
        )

        server.quit()

    except Exception as e:

        print(e)

# ==================================================
# PDF REPORT
# ==================================================

def generate_ticket_pdf(
    ticket_id,
    pci,
    condition,
    priority,
    repair
):

    pdf = FPDF()

    pdf.add_page()

    pdf.set_font(
        "Arial",
        size=14
    )

    pdf.cell(
        200,
        10,
        txt="Municipal Infrastructure Report",
        ln=True
    )

    pdf.ln(10)

    pdf.set_font(
        "Arial",
        size=12
    )

    pdf.cell(
        200,
        10,
        txt=f"Ticket ID : {ticket_id}",
        ln=True
    )

    pdf.cell(
        200,
        10,
        txt=f"PCI : {pci}",
        ln=True
    )

    pdf.cell(
        200,
        10,
        txt=f"Condition : {condition}",
        ln=True
    )

    pdf.cell(
        200,
        10,
        txt=f"Priority : {priority}",
        ln=True
    )

    pdf.multi_cell(
        0,
        10,
        txt=f"Recommended Repair : {repair}"
    )

    file_path = f"reports/{ticket_id}.pdf"

    pdf.output(file_path)

    return file_path

# ==================================================
# SIDEBAR
# ==================================================

st.sidebar.title(
    "Municipal Infrastructure AI"
)

app_mode = st.sidebar.radio(
    "Select Interface",
    [
        "Citizen Portal",
        "Admin Dashboard",
        "Contractor Portal"
    ]
)

# ==================================================
# CITIZEN PORTAL
# ==================================================

if app_mode == "Citizen Portal":

    st.title(
        "Road Damage Reporting System"
    )

    col1, col2 = st.columns(2)

    with col1:

        img_file = st.file_uploader(
            "Upload Road Image",
            type=["jpg", "jpeg", "png"]
        )

        cam_file = st.camera_input(
            "Capture Road Image"
        )

    with col2:

        email_in = st.text_input(
            "Email Address"
        )

        zone_in = st.selectbox(
            "Municipal Zone",
            [
                "North",
                "South",
                "East",
                "West",
                "Central"
            ]
        )

    lat_in = 12.9716
    lon_in = 77.5946

    st.subheader("Location")

    location_mode = st.radio(
        "Location Method",
        [
            "GPS",
            "Landmark",
            "Pin on Map"
        ]
    )

    if location_mode == "GPS":

        loc = get_geolocation()

        if loc and "coords" in loc:

            lat_in = loc["coords"]["latitude"]
            lon_in = loc["coords"]["longitude"]

            st.success(
                f"GPS Locked: {lat_in:.5f}, {lon_in:.5f}"
            )

    elif location_mode == "Landmark":

        landmark = st.text_input(
            "Enter Landmark"
        )

        if landmark:

            try:

                geolocator = Nominatim(
                    user_agent="municipal_ai"
                )

                location = geolocator.geocode(
                    landmark
                )

                if location:

                    lat_in = location.latitude
                    lon_in = location.longitude

                    st.success(
                        location.address
                    )

            except:
                pass
    elif location_mode == "Pin on Map":

        st.info(
            "Click on the map to mark the road damage location."
        )

        default_lat = 12.9716
        default_lon = 77.5946

        pin_map = folium.Map(
            location=[default_lat, default_lon],
            zoom_start=12
        )

        map_data = st_folium(
            pin_map,
            width=700,
            height=400,
            key="road_damage_pin"
        )

        if (
            map_data
            and
            map_data.get("last_clicked")
        ):

            lat_in = map_data["last_clicked"]["lat"]
            lon_in = map_data["last_clicked"]["lng"]

        st.success(
            f"Location Selected: {lat_in:.6f}, {lon_in:.6f}"
        )

    else:

        lat_in = default_lat
        lon_in = default_lon

        st.warning(
            "Click on the map to select a location."
        )
    # ==========================================
    # ANALYZE BUTTON
    # ==========================================

    if st.button(
        "Analyze & Generate Ticket"
    ):

        img_source = (
            cam_file
            if cam_file
            else img_file
        )

        if img_source is None:

            st.error(
                "Upload an image first."
            )

        elif model is None:

            st.error(
                "Model not loaded."
            )

        else:

            img = Image.open(
                img_source
            )

            img.save(
                "temp.jpg"
            )

            results = model(
                "temp.jpg"
            )

            counts = {
                "potholes": 0,
                "transverse": 0,
                "longitudinal": 0,
                "alligator": 0
            }

            severity_counts = {

                "pothole_high": 0,
                "pothole_medium": 0,
                "pothole_low": 0,

                "transverse_high": 0,
                "transverse_medium": 0,
                "transverse_low": 0,

                "longitudinal_high": 0,
                "longitudinal_medium": 0,
                "longitudinal_low": 0,

                "alligator_high": 0,
                "alligator_medium": 0,
                "alligator_low": 0
            }

            for box in results[0].boxes:

                conf = float(
                    box.conf[0]
                )

                if conf < 0.40:
                    continue

                cls_id = int(
                    box.cls[0]
                )

                label = model.names[
                    cls_id
                ].lower()

                severity = get_severity(
                    conf
                )

                if "pothole" in label:

                    counts["potholes"] += 1
                    severity_counts[
                        f"pothole_{severity.lower()}"
                    ] += 1

                elif "transverse" in label:

                    counts["transverse"] += 1
                    severity_counts[
                        f"transverse_{severity.lower()}"
                    ] += 1

                elif "longitudinal" in label:

                    counts["longitudinal"] += 1
                    severity_counts[
                        f"longitudinal_{severity.lower()}"
                    ] += 1

                elif (
                    "alligator" in label
                    or
                    "aligator" in label
                ):

                    counts["alligator"] += 1

                    severity_counts[
                        f"alligator_{severity.lower()}"
                    ] += 1

            pci, condition, priority, repair, repair_rank, repair_reason = (
                calculate_engineering_metrics(
                    counts,
                    severity_counts
                )
            )

            duplicate, existing = is_duplicate(
                lat_in,
                lon_in
            )

            if duplicate:

                st.warning(
                    f"Possible Duplicate Complaint Found: {existing}"
                )

            ticket_id = (
                "TKT"
                + str(
                    random.randint(
                        10000,
                        99999
                    )
                )
            )

            c.execute(
                """
                INSERT INTO tickets
                (
                    ticket_id,
                    email,
                    date,
                    lat,
                    lon,
                    zone,
                    potholes,
                    transverse,
                    longitudinal,
                    alligator,
                    pci,
                    condition,
                    priority,
                    action,
                    status
                )
                VALUES
                (
                    ?,?,?,?,?,?,
                    ?,?,?,?,
                    ?,?,?,?,
                    ?
                )
                """,
                (
                    ticket_id,
                    email_in,
                    datetime.now().strftime("%d-%m-%Y"),
                    lat_in,
                    lon_in,
                    zone_in,
                    counts["potholes"],
                    counts["transverse"],
                    counts["longitudinal"],
                    counts["alligator"],
                    pci,
                    condition,
                    priority,
                    repair,
                    "Pending Review"
                )
            )

            conn.commit()

            pdf_file = generate_ticket_pdf(
                ticket_id,
                pci,
                condition,
                priority,
                repair
            )

            st.success(
                f"Ticket Generated: {ticket_id}"
            )

            st.image(
                results[0].plot(),
                channels="BGR"
            )

            st.metric(
                "PCI Score",
                pci
            )

            st.write(
                f"Condition : {condition}"
            )

            st.write(
                f"Priority : {priority}"
            )

            st.write(
                f"Repair : {repair}"
            )

            st.write(
                f"Reason : {repair_reason}"
            )

            with open(
                pdf_file,
                "rb"
            ) as file:

                st.download_button(
                    "Download Report",
                    data=file,
                    file_name=f"{ticket_id}.pdf"
                )
    # ==================================================
    # CITIZEN SERVICES
    # ==================================================

    st.divider()

    st.header(
         "Citizen Services"
    )

    service_tab1, service_tab2 = st.tabs(
        [
            "Track Complaint",
            "AI Feedback"
       ]
)

    # ==================================================
    # TRACK COMPLAINT
    # ==================================================

    with service_tab1:

        track_id = st.text_input(
            "Enter Ticket ID"
        )

        if st.button(
            "Track Status"
        ):

            result = pd.read_sql(
                f"""
                SELECT
                    ticket_id,
                    zone,
                    pci,
                    condition,
                    priority,
                    status,
                    contractor,
                    deadline
                FROM tickets
                WHERE ticket_id='{track_id}'
                """,
                conn
            )

            if not result.empty:

                st.dataframe(
                    result,
                    use_container_width=True
                )

            else:
    
                st.warning(
                    "Ticket Not Found"
                )

    # ==================================================
    # AI FEEDBACK ENGINE
    # ==================================================

    with service_tab2:

        feedback_ticket = st.text_input(
            "Ticket ID"
        )

        feedback_text = st.text_area(
            "AI Misclassification Feedback"
        )

        if st.button(
            "Submit Feedback"
        ):

            exists = c.execute(
                """
                SELECT ticket_id
                FROM tickets
                WHERE ticket_id=?
                """,
                (
                    feedback_ticket,
                )
            ).fetchone()

            if exists:

                c.execute(
                    """
                    UPDATE tickets
                    SET user_feedback=?
                    WHERE ticket_id=?
                    """,
                    (
                        feedback_text,
                        feedback_ticket
                    )
                )

                conn.commit()

                st.success(
                    "Feedback Submitted"
                )

            else:
    
                st.error(
                    "Ticket Not Found"
                )            
# ==================================================
# ADMIN DASHBOARD
# ==================================================

elif app_mode == "Admin Dashboard":

    st.title(
        "Municipal Operations Dashboard"
    )

    admin_password = st.sidebar.text_input(
        "Admin Password",
        type="password"
    )

    if admin_password != "1234":

        st.warning(
            "Enter Admin Password"
        )

    else:

        df = pd.read_sql(
            "SELECT * FROM tickets",
            conn
        )

        if df.empty:

            st.info(
                "No complaints available."
            )

        else:

            # ==========================================
            # KPI SECTION
            # ==========================================

            st.subheader(
                "System Overview"
            )

            col1, col2, col3, col4 = st.columns(4)

            with col1:

                st.metric(
                    "Total Complaints",
                    len(df)
                )

            with col2:

                st.metric(
                    "Average PCI",
                    round(df["pci"].mean(), 2)
                )

            with col3:

                critical_count = len(
                    df[df["priority"] == "Critical"]
                )

                st.metric(
                    "Critical Roads",
                    critical_count
                )

            with col4:

                resolved_count = len(
                    df[df["status"] == "Resolved"]
                )

                st.metric(
                    "Resolved",
                    resolved_count
                )

            st.divider()

            # ==========================================
            # GIS MAP
            # ==========================================

            st.subheader(
                "Road Defect GIS Map"
            )

            center_lat = df.iloc[-1]["lat"]
            center_lon = df.iloc[-1]["lon"]

            m = folium.Map(
                location=[
                    center_lat,
                    center_lon
                ],
                zoom_start=12
            )

            for _, row in df.iterrows():

                if row["priority"] == "Critical":

                    color = "red"

                elif row["priority"] == "High":

                    color = "orange"

                else:

                    color = "green"

                popup_text = f"""
                Ticket : {row['ticket_id']}
                <br>
                PCI : {row['pci']}
                <br>
                Status : {row['status']}
                <br>
                Zone : {row['zone']}
                """

                folium.CircleMarker(
                    location=[
                        row["lat"],
                        row["lon"]
                    ],
                    radius=8,
                    color=color,
                    fill=True,
                    fill_color=color,
                    popup=popup_text
                ).add_to(m)

            st_folium(
                m,
                width=1200,
                height=500
            )

            st.divider()

            # ==========================================
            # GIS HEATMAP
            # ==========================================

            st.subheader(
                "Road Damage Heatmap"
            )

            heatmap = folium.Map(
                location=[
                    center_lat,
                    center_lon
                ],
                zoom_start=12
            )

            heat_data = []

            for _, row in df.iterrows():

                heat_data.append(
                    [
                        row["lat"],
                        row["lon"]
                    ]
                )

            HeatMap(
                heat_data,
                radius=20,
                blur=15
            ).add_to(
                heatmap
            )

            st_folium(
                heatmap,
                width=1200,
                height=500,
                key="heatmap"
            )

            st.divider()

            # ==========================================
            # ZONE ANALYTICS
            # ==========================================

            st.subheader(
                "Zone Analytics"
            )

            zone_summary = (
                df.groupby("zone")
                .agg(
                    complaints=("ticket_id", "count"),
                    avg_pci=("pci", "mean")
                )
                .reset_index()
            )

            st.dataframe(
                zone_summary,
                use_container_width=True
            )

            st.divider()

            # ==========================================
            # CRITICAL ZONE ANALYSIS
            # ==========================================

            st.subheader(
                "Critical Zone Ranking"
            )

            critical_df = (
                df[
                    df["priority"] == "Critical"
                ]
                .groupby("zone")
                .size()
                .reset_index(
                    name="critical_count"
                )
            )

            if not critical_df.empty:

                st.dataframe(
                    critical_df.sort_values(
                        "critical_count",
                        ascending=False
                    ),
                    use_container_width=True
                )

            else:

                st.info(
                    "No critical roads currently."
                )

            st.divider()

            # ==========================================
            # DAMAGE ANALYTICS
            # ==========================================

            st.subheader(
                "Damage Statistics"
            )

            damage_df = pd.DataFrame({

                "Damage Type": [
                    "Potholes",
                    "Longitudinal",
                    "Transverse",
                    "Alligator"
                ],

                "Count": [

                    df["potholes"].sum(),

                    df["longitudinal"].sum(),

                    df["transverse"].sum(),

                    df["alligator"].sum()
                ]
            })

            st.bar_chart(
                damage_df.set_index(
                    "Damage Type"
                )
            )

            st.divider()

            # ==========================================
            # PRIORITY ANALYSIS
            # ==========================================

            st.subheader(
                "Priority Distribution"
            )

            priority_df = (
                df.groupby("priority")
                .size()
                .reset_index(
                    name="count"
                )
            )

            st.bar_chart(
                priority_df.set_index(
                    "priority"
                )
            )

            st.divider()

            # ==========================================
            # STATUS UPDATE
            # ==========================================

            st.subheader(
                "Update Complaint Status"
            )

            selected_ticket = st.selectbox(
                "Select Ticket",
                df["ticket_id"]
            )

            new_status = st.selectbox(
                "New Status",
                [
                    "Pending Review",
                    "Assigned",
                    "In Progress",
                    "Material Procurement",
                    "Resolved"
                ]
            )

            if st.button(
                "Update Status"
            ):

                c.execute(
                    """
                    UPDATE tickets
                    SET status=?
                    WHERE ticket_id=?
                    """,
                    (
                        new_status,
                        selected_ticket
                    )
                )

                conn.commit()

                st.success(
                    "Status Updated"
                )

                st.rerun()

            st.divider()

            # ==========================================
            # WORK ORDER ASSIGNMENT
            # ==========================================

            st.subheader(
                "Assign Contractor"
            )

            assign_ticket = st.selectbox(
                "Ticket",
                df["ticket_id"],
                key="assign_ticket"
            )

            contractor = st.selectbox(
                "Contractor",
                [
                    "Team Alpha",
                    "Team Bravo",
                    "Team Charlie"
                ]
            )

            deadline = st.date_input(
                "Deadline"
            )

            if st.button(
                "Assign Work Order"
            ):

                c.execute(
                    """
                    UPDATE tickets
                    SET contractor=?,
                        deadline=?,
                        status='Assigned'
                    WHERE ticket_id=?
                    """,
                    (
                        contractor,
                        deadline.strftime(
                            "%Y-%m-%d"
                        ),
                        assign_ticket
                    )
                )

                conn.commit()

                st.success(
                    "Work Order Assigned"
                )

                st.rerun()

            st.divider()

            # ==========================================
            # COMPLETE DATABASE VIEW
            # ==========================================

            st.subheader(
                "All Complaints"
            )

            st.dataframe(
                df,
                use_container_width=True
            )
# ==================================================
# CONTRACTOR PORTAL
# ==================================================

elif app_mode == "Contractor Portal":

    st.title(
        "Contractor Operations Portal"
    )

    contractor_id = st.selectbox(
        "Select Team",
        [
            "Team Alpha",
            "Team Bravo",
            "Team Charlie"
        ]
    )

    contractor_df = pd.read_sql(
        f"""
        SELECT
            ticket_id,
            zone,
            action,
            deadline,
            status
        FROM tickets
        WHERE contractor='{contractor_id}'
        """,
        conn
    )

    st.subheader(
        "Assigned Work Orders"
    )

    st.dataframe(
        contractor_df,
        use_container_width=True
    )

    st.divider()

    st.subheader(
        "Close Work Order"
    )

    pending_tasks = contractor_df[
        contractor_df["status"] != "Resolved"
    ]

    if not pending_tasks.empty:

        selected_task = st.selectbox(
            "Select Ticket",
            pending_tasks["ticket_id"]
        )

        repair_photo = st.file_uploader(
            "Upload Repair Photo",
            type=["jpg", "jpeg", "png"]
        )

        completion_notes = st.text_area(
            "Completion Notes"
        )

        if st.button(
            "Mark as Resolved"
        ):

            c.execute(
                """
                UPDATE tickets
                SET status='Resolved'
                WHERE ticket_id=?
                """,
                (
                    selected_task,
                )
            )

            conn.commit()

            citizen_email = c.execute(
                """
                SELECT email
                FROM tickets
                WHERE ticket_id=?
                """,
                (
                    selected_task,
                )
            ).fetchone()

            if citizen_email:

                send_email(
                    citizen_email[0],
                    "Road Repair Completed",
                    f"""
                    Your complaint
                    {selected_task}
                    has been resolved.

                    Notes:
                    {completion_notes}
                    """
                )

            st.success(
                "Work Order Closed"
            )

            st.rerun()

    else:

        st.success(
            "No Pending Tasks"
        )


# ==================================================
# PCI TREND ANALYTICS
# ==================================================

st.divider()

st.header(
    "Municipal Performance Analytics"
)

try:

    analytics_df = pd.read_sql(
        """
        SELECT
            date,
            pci
        FROM tickets
        """,
        conn
    )

    if not analytics_df.empty:

        analytics_df["date"] = pd.to_datetime(
            analytics_df["date"],
            dayfirst=True,
            errors="coerce"
        )

        analytics_df = analytics_df.sort_values(
            "date"
        )

        st.subheader(
            "PCI Trend"
        )

        trend_df = analytics_df[
            ["date", "pci"]
        ].set_index(
            "date"
        )

        st.line_chart(
            trend_df
        )

except:
    pass
st.markdown("""
<style>

/* ===== Main Background ===== */
.stApp {
    background: linear-gradient(
        135deg,
        #f0f9ff 0%,
        #e0f2fe 25%,
        #dbeafe 50%,
        #ede9fe 100%
    );
}

/* ===== Sidebar ===== */
[data-testid="stSidebar"] {
    background: linear-gradient(
        180deg,
        #0f172a,
        #1e293b
    );
}

[data-testid="stSidebar"] * {
    color: white !important;
}

/* ===== Main Titles ===== */
h1 {
    background: linear-gradient(
        90deg,
        #2563eb,
        #06b6d4,
        #10b981
    );

    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;

    font-size: 3rem;
    font-weight: 800;
}

/* ===== Section Headers ===== */
h2,h3 {
    color: #1e3a8a;
}

/* ===== Cards ===== */
div[data-testid="stVerticalBlock"] > div {
    border-radius: 15px;
}

/* ===== Buttons ===== */
.stButton > button {

    background: linear-gradient(
        90deg,
        #2563eb,
        #06b6d4
    );

    color: white;
    border: none;
    border-radius: 12px;

    padding: 10px 20px;

    font-weight: 700;

    transition: 0.3s;
}

.stButton > button:hover {

    transform: scale(1.03);

    background: linear-gradient(
        90deg,
        #1d4ed8,
        #0891b2
    );
}

/* ===== Success Box ===== */
.stSuccess {
    border-radius: 12px;
}

/* ===== Warning Box ===== */
.stWarning {
    border-radius: 12px;
}

/* ===== Metric Cards ===== */
[data-testid="metric-container"] {

    background: white;

    border-radius: 15px;

    padding: 15px;

    box-shadow:
        0 4px 12px rgba(0,0,0,0.12);

    border-left: 6px solid #2563eb;
}

/* ===== DataFrames ===== */
[data-testid="stDataFrame"] {

    background: white;

    border-radius: 15px;

    padding: 10px;

    box-shadow:
        0 4px 12px rgba(0,0,0,0.10);
}

/* ===== File Uploader ===== */
[data-testid="stFileUploader"] {

    background: white;

    border-radius: 15px;

    padding: 10px;

    border: 2px dashed #3b82f6;
}

/* ===== Tabs ===== */
button[data-baseweb="tab"] {

    font-weight: 700;

    border-radius: 10px;

    margin-right: 5px;
}

/* ===== KPI Cards ===== */
.kpi-card {

    background: white;

    padding: 20px;

    border-radius: 15px;

    text-align: center;

    box-shadow:
        0 5px 15px rgba(0,0,0,0.12);
}

</style>
""", unsafe_allow_html=True)
