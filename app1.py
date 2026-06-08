import streamlit as st
import pandas as pd
import sqlite3
import random
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from fpdf import FPDF
import os
import folium
from streamlit_folium import st_folium
from ultralytics import YOLO
from PIL import Image
from streamlit_js_eval import get_geolocation
from geopy.geocoders import Nominatim

# ==========================================
# 1. PLATFORM CONFIGURATION & DATABASE
# ==========================================
st.set_page_config(page_title="Municipal Infrastructure AI", layout="wide")
os.makedirs("reports", exist_ok=True)

SENDER_EMAIL = "pvsnkeerthivardhan08@gmail.com"
APP_PASSWORD = "iugt wcto jojb uqpb"
AUTHORITY_EMAIL = "pvsnkeerthivardhan43@gmail.com"

@st.cache_resource
def load_model():
    try:
        return YOLO("finalv3.pt")
    except Exception as e:
        st.error(f"Model loading failed: {e}")
        return None

model = load_model()

def init_db():
    conn = sqlite3.connect("municipal_operations.db", check_same_thread=False)
    c = conn.cursor()
    
    # Schema includes the user_feedback column
    c.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id TEXT UNIQUE, email TEXT, date TEXT, lat FLOAT, lon FLOAT, zone TEXT,
        potholes INTEGER, transverse INTEGER, longitudinal INTEGER, alligator INTEGER,
        pci INTEGER, condition TEXT, priority TEXT, action TEXT, 
        status TEXT, contractor TEXT, deadline TEXT, user_feedback TEXT
    )
    """)
    
    try:
        c.execute("ALTER TABLE tickets ADD COLUMN user_feedback TEXT")
    except sqlite3.OperationalError:
        pass 
        
    conn.commit()
    return conn, c

conn, c = init_db()
# ==========================================
# CUSTOM UI THEME (CSS INJECTION)
# ==========================================
st.markdown("""
    <style>
    /* Main background color (light slate blue) */
    .stApp {
        background-color: #f8fafc;
    }
    
    /* Give the sidebar a darker, professional contrast */
    [data-testid="stSidebar"] {
        background-color: #1e293b;
    }
    
    /* Make the sidebar text white so it's readable */
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    
    /* Make the main titles pop with a gradient */
    h1 {
        background: -webkit-linear-gradient(45deg, #2563eb, #10b981);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }
    
    /* Style the primary buttons to stand out */
    .stButton>button {
        background-color: #3b82f6;
        color: white;
        border-radius: 8px;
        border: none;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    /* Make the button darker on hover */
    .stButton>button:hover {
        background-color: #2563eb;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)
# ==========================================
# 2. CIVIL ENGINEERING & AI LOGIC
# ==========================================
def calculate_engineering_metrics(counts):
    pci = 100 - (counts['longitudinal'] * 5 + counts['transverse'] * 8 + counts['potholes'] * 18 + counts['alligator'] * 30)
    pci = max(0, pci)
    
    if pci >= 85: cond = "Excellent"
    elif pci >= 70: cond = "Good"
    elif pci >= 55: cond = "Fair"
    elif pci >= 40: cond = "Poor"
    elif pci >= 20: cond = "Very Poor"
    else: cond = "Failed"
    
    if counts['alligator'] >= 1: 
        prio, act = "Critical", "Immediate Structural Rehabilitation Required"
    elif counts['potholes'] >= 1: 
        prio, act = "High", "Immediate Pothole Repair Required"
    elif pci < 40: 
        prio, act = "High", "Major Rehabilitation Required"
    elif pci < 60: 
        prio, act = "Medium", "Preventive Maintenance Required"
    else: 
        prio, act = "Low", "Routine Monitoring"
        
    return pci, cond, prio, act

# ==========================================
# 3. AUTOMATION LOGIC (PDF & EMAIL)
# ==========================================
def send_email(to_email, subject, body):
    if not to_email: return
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        msg = MIMEText(body)
        msg["Subject"], msg["From"], msg["To"] = subject, SENDER_EMAIL, to_email
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Email failed: {e}")

def generate_ticket_pdf(ticket_id, pci, condition, priority, action):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=16)
    pdf.cell(200, 10, txt="Road Damage Inspection Report", ln=True)
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Ticket ID: {ticket_id}", ln=True)
    pdf.cell(200, 10, txt=f"PCI Score: {pci}", ln=True)
    pdf.cell(200, 10, txt=f"Road Condition: {condition}", ln=True)
    pdf.cell(200, 10, txt=f"Priority Level: {priority}", ln=True)
    pdf.multi_cell(0, 10, txt=f"Municipality Action Plan: {action}")
    
    report_path = f"reports/{ticket_id}.pdf"
    pdf.output(report_path)
    return report_path

# ==========================================
# 4. PORTAL NAVIGATION (THE UI)
# ==========================================
st.sidebar.title("🚧 Infrastructure Portal")
app_mode = st.sidebar.radio("Select Interface", ["Citizen Portal", "Admin & GIS Dashboard", "Contractor Portal"])

# ------------------------------------------
# A. CITIZEN PORTAL
# ------------------------------------------
if app_mode == "Citizen Portal":
    st.title("Citizen Reporting Dashboard")
    st.markdown("Upload images of road defects. The AI will automatically assess severity and generate a ticket.")
    
    col1, col2 = st.columns(2)
    with col1:
        img_file = st.file_uploader("Upload Road Image", type=['jpg', 'png', 'jpeg'])
        camera_file = st.camera_input("Or take a picture live")
        
    with col2:
        email_in = st.text_input("Your Email (For Status Updates)")
        zone_in = st.selectbox("Municipal Zone", ["North", "South", "East", "West", "Central"])
        
        # --- NEW 3-WAY LOCATION ENGINE ---
        st.markdown("### Location Data")
        loc_method = st.radio("Location Method", ["Use Live Device GPS", "Search by Landmark", "Pinpoint on Map"])
        
        lat_in, lon_in = 12.9716, 77.5946 
        
        ZONE_CENTERS = {
            "North": (13.0354, 77.5988),
            "South": (12.9259, 77.5800),
            "East": (12.9716, 77.6411),
            "West": (12.9783, 77.5401),
            "Central": (12.9716, 77.5946)
        }
        
        if loc_method == "Use Live Device GPS":
            loc = get_geolocation()
            if loc and 'coords' in loc:
                lat_in = loc['coords']['latitude']
                lon_in = loc['coords']['longitude']
                st.success(f"📍 GPS Locked: {lat_in:.5f}, {lon_in:.5f}")
            elif loc and 'error' in loc:
                st.error("GPS Access Denied by Browser. Please allow location permissions.")
            else:
                st.info("🛰️ Fetching live coordinates... (Please click 'Allow' if your browser prompts you)")
                
        elif loc_method == "Search by Landmark":
            manual_landmark = st.text_input("Enter Landmark or Street Name", placeholder="e.g., DSCE,Majestic")
            if manual_landmark:
                try:
                    search_term = manual_landmark.lower()
                    CUSTOM_LANDMARKS = {
                        "dsce": (12.9081, 77.5553), "dayananda sagar": (12.9081, 77.5553),
                        "rvce": (12.9239, 77.4997), "pesu": (12.9333, 77.5354),
                        "bmsce": (12.9410, 77.5655), "majestic": (12.9766, 77.5713),
                        "vidhana soudha": (12.9796, 77.5906), "silk board": (12.9176, 77.6238)
                    }
                    
                    found_internal = False
                    for key, coords in CUSTOM_LANDMARKS.items():
                        if key in search_term:
                            lat_in, lon_in = coords
                            st.success(f"📍 Mapped to: {key.title()} (CENTRAL))")
                            found_internal = True
                            break
                    
                    if not found_internal:
                        geolocator = Nominatim(user_agent="municipal_infra_app")
                        location = geolocator.geocode(f"{manual_landmark}, {zone_in}, Bengaluru") or geolocator.geocode(f"{manual_landmark}, Bengaluru") or geolocator.geocode(manual_landmark)
                        
                        if location:
                            lat_in, lon_in = location.latitude, location.longitude
                            st.success(f"📍 Mapped to: {location.address}")
                        else:
                            lat_in, lon_in = ZONE_CENTERS[zone_in]
                            st.warning(f"Exact landmark not found. Dropping pin at center of {zone_in} Zone.")
                            
                except Exception as e:
                    lat_in, lon_in = ZONE_CENTERS[zone_in]
                    st.warning(f"Geocoding offline. Dropping pin at center of {zone_in} Zone.")

        elif loc_method == "Pinpoint on Map":
            st.markdown("Click directly on the map to place your pin.")
            start_lat, start_lon = ZONE_CENTERS[zone_in]
            
            # Create a mini interactive map for selection
            m_select = folium.Map(location=[start_lat, start_lon], zoom_start=12)
            folium.Marker([start_lat, start_lon], tooltip=f"{zone_in} Zone Center").add_to(m_select)
            
            # Render map and catch click data
            map_data = st_folium(m_select, height=300, width=500, key="select_map")
            
            if map_data and map_data.get("last_clicked"):
                lat_in = map_data["last_clicked"]["lat"]
                lon_in = map_data["last_clicked"]["lng"]
                st.success(f"📍 Manual Pin Dropped: {lat_in:.5f}, {lon_in:.5f}")
            else:
                lat_in, lon_in = start_lat, start_lon
                st.info("Waiting for you to click a location on the map...")

        
    if st.button("Analyze & Report", type="primary"):
        img_source = camera_file if camera_file else img_file
        if img_source and model:
            with st.spinner("AI is analyzing road surface..."):
                img = Image.open(img_source)
                img.save("temp.jpg")
                results = model("temp.jpg")
                
                counts = {"potholes": 0, "transverse": 0, "longitudinal": 0, "alligator": 0}
                for box in results[0].boxes:
                    label = model.names[int(box.cls[0])].lower()
                    if "pothole" in label: counts["potholes"] += 1
                    elif "transverse" in label: counts["transverse"] += 1
                    elif "longitudinal" in label: counts["longitudinal"] += 1
                    elif "alligator" in label: counts["alligator"] += 1
                        
                pci, cond, prio, act = calculate_engineering_metrics(counts)
                tkt_id = f"TKT{random.randint(10000, 99999)}"
                
                # Insert includes NULL for user_feedback
                c.execute("""
                INSERT INTO tickets (ticket_id, email, date, lat, lon, zone, potholes, transverse, longitudinal, alligator, pci, condition, priority, action, status, user_feedback) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending Review', NULL)
                """, (tkt_id, email_in, datetime.now().strftime("%d-%m-%Y"), lat_in, lon_in, zone_in, counts['potholes'], counts['transverse'], counts['longitudinal'], counts['alligator'], pci, cond, prio, act))
                conn.commit()
                
                send_email(email_in, "Road Defect Logged", f"Complaint Registered.\nTicket ID: {tkt_id}\nPCI Score: {pci}\nMunicipality Action: {act}")
                
                if prio in ["Critical", "High"] or counts['alligator'] >= 1 or counts['potholes'] >= 1:
                    send_email(AUTHORITY_EMAIL, "URGENT MUNICIPALITY ALERT", f"Critical damage detected.\nTicket: {tkt_id}\nLocation: {lat_in:.4f}, {lon_in:.4f} ({zone_in})\nPCI: {pci}\nAction: {act}\nImmediate inspection required.")
                
                pdf_path = generate_ticket_pdf(tkt_id, pci, cond, prio, act)
                
            st.success("Report Submitted Successfully!")
            
            formatted_result = f"""Ticket ID: {tkt_id}

Location: {lat_in:.5f}, {lon_in:.5f} ({zone_in})

Potholes Detected: {counts['potholes']}
Transverse Cracks: {counts['transverse']}
Longitudinal Cracks: {counts['longitudinal']}
Alligator Cracks: {counts['alligator']}

PCI Score: {pci}

Road Condition: {cond}

Priority Level: {prio}

Municipality Action:
{act}

Repair Status:
Pending Review"""

            st.text(formatted_result)
            st.image(results[0].plot(), caption="AI Detection Map", channels="BGR")
            
            with open(pdf_path, "rb") as file:
                st.download_button("Download PDF Report", data=file, file_name=f"{tkt_id}.pdf", mime="application/pdf")

    st.divider()
    
    col_track1, col_track2 = st.columns(2)
    with col_track1:
        st.subheader("🔍 Track Complaint")
        track_id = st.text_input("Enter Ticket ID")
        if st.button("Track Status"):
            df_track = pd.read_sql(f"SELECT ticket_id, pci, priority, status, contractor, user_feedback FROM tickets WHERE ticket_id='{track_id}'", conn)
            if not df_track.empty: st.dataframe(df_track, use_container_width=True)
            else: st.warning("Ticket not found.")
            
    with col_track2:
        st.subheader("⚠️ AI Feedback Engine")
        st.write("Did the AI miss a pothole or misclassify a crack? Let us know.")
        fb_tkt = st.text_input("Ticket ID to Correct")
        fb_text = st.text_area("What did the AI get wrong?")
        if st.button("Submit Correction to Admin"):
            exists = c.execute("SELECT 1 FROM tickets WHERE ticket_id=?", (fb_tkt,)).fetchone()
            if not exists:
                st.error("Ticket not found. Please check your Ticket ID.")
            else:
                c.execute("UPDATE tickets SET user_feedback=? WHERE ticket_id=?", (fb_text, fb_tkt))
                conn.commit()
                st.success(f"Feedback for {fb_tkt} recorded for manual admin review.")

# ------------------------------------------
# B. ADMIN & GIS DASHBOARD
# ------------------------------------------
elif app_mode == "Admin & GIS Dashboard":
    st.title("Municipal Operations & GIS Dashboard")
    
    admin_pass = st.sidebar.text_input("Admin Password", type="password")
    
    if admin_pass == "1234":
        df = pd.read_sql("SELECT * FROM tickets", conn)
        
        if not df.empty:
            st.subheader("Live Defect Map")
            latest_lat = df.iloc[-1]['lat']
            latest_lon = df.iloc[-1]['lon']
            m = folium.Map(location=[latest_lat, latest_lon], zoom_start=12) 
            
            for idx, row in df.iterrows():
                color = "red" if row['priority'] == "Critical" else ("orange" if row['priority'] == "High" else "green")
                folium.CircleMarker(
                    location=[row['lat'], row['lon']], radius=8, color=color, fill=True, fill_color=color,
                    popup=f"<b>{row['ticket_id']}</b><br>PCI: {row['pci']}<br>Status: {row['status']}"
                ).add_to(m)
                
            st_folium(m, width=1200, height=450)
            
            st.divider()
            
            st.subheader("Manual Status Update & Citizen Notification")
            col_stat1, col_stat2, col_stat3 = st.columns([2, 2, 1])
            with col_stat1:
                target_ticket = st.selectbox("Select Ticket", df['ticket_id'])
            with col_stat2:
                new_status = st.selectbox("Update Status To", ["Pending Review", "In Progress", "Material Procurement", "Resolved"])
            with col_stat3:
                st.write("")
                st.write("")
                if st.button("Update & Notify User", use_container_width=True):
                    c.execute("UPDATE tickets SET status=? WHERE ticket_id=?", (new_status, target_ticket))
                    conn.commit()
                    user_email = df[df['ticket_id'] == target_ticket]['email'].values[0]
                    if user_email:
                        send_email(user_email, "Ticket Status Update", f"Hello, your road complaint {target_ticket} has been updated to: {new_status}.")
                    st.success(f"Status changed to '{new_status}'. Citizen notified via email!")
                    st.rerun()

            st.divider()
            
            st.subheader("Automated Work Order Assignment")
            
            # Displays the full database including User Feedback column
            st.dataframe(df[['ticket_id', 'zone', 'priority', 'status', 'contractor', 'user_feedback']], use_container_width=True)
            
            assign_col1, assign_col2, assign_col3 = st.columns(3)
            with assign_col1:
                assign_ticket = st.selectbox("Ticket to Assign", df[df['status'] != 'Resolved']['ticket_id'], key="assign")
            with assign_col2:
                contractor_assign = st.selectbox("Assign Team", ["Team Alpha (North)", "Team Bravo (South)", "Contractor XYZ"])
            with assign_col3:
                deadline_assign = st.date_input("Set Deadline")
                
            if st.button("Assign Work Order"):
                c.execute("UPDATE tickets SET status='Assigned', contractor=?, deadline=? WHERE ticket_id=?", (contractor_assign, deadline_assign.strftime("%Y-%m-%d"), assign_ticket))
                conn.commit()
                st.success(f"Work Order generated for {assign_ticket}.")
                st.rerun()
        else:
            st.info("📭 The database is currently empty. No road defects have been reported yet.")
    else:
        st.warning("🔒 Please enter the admin password in the sidebar to access the Municipal Dashboard.")

# ------------------------------------------
# C. CONTRACTOR PORTAL
# ------------------------------------------
elif app_mode == "Contractor Portal":
    st.title("Contractor Field Operations")
    
    contractor_id = st.selectbox("Select Your Team", ["Team Alpha (North)", "Team Bravo (South)", "Contractor XYZ"])
    df_contractor = pd.read_sql(f"SELECT ticket_id, action, deadline, status FROM tickets WHERE contractor='{contractor_id}'", conn)
    
    st.subheader(f"Assigned Tasks")
    st.dataframe(df_contractor, use_container_width=True)
    
    st.divider()
    st.subheader("Submit Completion Report")
    task_to_close = st.selectbox("Select Task to Close", df_contractor[df_contractor['status'] != 'Resolved']['ticket_id'] if not df_contractor.empty else ["No Pending Tasks"])
    repair_img = st.file_uploader("Upload 'After' Repair Photo", type=['jpg', 'png'])
    completion_notes = st.text_area("Completion Notes / Materials Used")
    
    if st.button("Mark as Resolved & Notify Citizen", type="primary"):
        if task_to_close and task_to_close != "No Pending Tasks":
            c.execute("UPDATE tickets SET status='Resolved' WHERE ticket_id=?", (task_to_close,))
            conn.commit()
            
            citizen_email = c.execute("SELECT email FROM tickets WHERE ticket_id=?", (task_to_close,)).fetchone()[0]
            if citizen_email:
                send_email(citizen_email, "Road Repair Completed", f"Your ticket {task_to_close} has been fully resolved by {contractor_id}.\nNotes: {completion_notes}")
            
            st.success(f"Task {task_to_close} closed. Automated email sent to citizen.")
            st.rerun()
