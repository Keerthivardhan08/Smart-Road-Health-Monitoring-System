import gradio as gr
from ultralytics import YOLO
import sqlite3
import pandas as pd
import random
from datetime import datetime
from fpdf import FPDF
import smtplib
from email.mime.text import MIMEText
import os

# ==========================================
# CREATE REPORT FOLDER
# ==========================================

os.makedirs("reports", exist_ok=True)

# ==========================================
# LOAD YOLO MODEL
# ==========================================

# Replace with your trained model
model = YOLO("finalv3.pt")

# TEMPORARY OPTION:
# model = YOLO("yolov8n.pt")

# ==========================================
# DATABASE SETUP
# ==========================================

conn = sqlite3.connect(
    "road_damage.db",
    check_same_thread=False
)

c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT,
    date TEXT,
    location TEXT,
    potholes INTEGER,
    transverse INTEGER,
    longitudinal INTEGER,
    alligator INTEGER,
    pci INTEGER,
    condition TEXT,
    priority TEXT,
    action TEXT,
    status TEXT
)
""")

conn.commit()

# ==========================================
# ADMIN LOGIN
# ==========================================

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"

# ==========================================
# AUTHORITY EMAIL
# ==========================================

AUTHORITY_EMAIL = "authority@gmail.com"

# ==========================================
# EMAIL CONFIGURATION
# ==========================================

SENDER_EMAIL = "yourgmail@gmail.com"
APP_PASSWORD = "your_app_password"

# ==========================================
# ADMIN LOGIN FUNCTION
# ==========================================

def admin_login(username, password):

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:

        df = pd.read_sql(
            "SELECT * FROM complaints",
            conn
        )

        return (
            "Login Successful",
            gr.update(visible=True),
            df
        )

    else:

        return (
            "Invalid Username or Password",
            gr.update(visible=False),
            None
        )

# ==========================================
# USER EMAIL
# ==========================================

def send_email(
    receiver_email,
    ticket_id,
    pci,
    action
):

    subject = "Road Damage Complaint Registered"

    body = f"""
Complaint Registered Successfully

Ticket ID: {ticket_id}

PCI Score: {pci}

Municipality Action:
{action}
"""

    msg = MIMEText(body)

    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = receiver_email

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

        server.sendmail(
            SENDER_EMAIL,
            receiver_email,
            msg.as_string()
        )

        server.quit()

    except:

        print("Citizen email failed")

# ==========================================
# CRITICAL ALERT EMAIL
# ==========================================

def send_critical_alert(
    ticket_id,
    location,
    pci,
    priority,
    action
):

    subject = "CRITICAL ROAD DAMAGE ALERT"

    body = f"""
URGENT MUNICIPALITY ALERT

Critical road damage detected.

Ticket ID:
{ticket_id}

Location:
{location}

PCI Score:
{pci}

Priority:
{priority}

Recommended Action:
{action}

Immediate inspection required.
"""

    msg = MIMEText(body)

    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = AUTHORITY_EMAIL

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

        server.sendmail(
            SENDER_EMAIL,
            AUTHORITY_EMAIL,
            msg.as_string()
        )

        server.quit()

        print("Critical alert sent")

    except:

        print("Critical alert failed")

# ==========================================
# PDF REPORT
# ==========================================

def generate_pdf(
    ticket_id,
    location,
    pci,
    condition,
    priority,
    action
):

    pdf = FPDF()

    pdf.add_page()

    pdf.set_font("Arial", size=16)

    pdf.cell(
        200,
        10,
        txt="Road Damage Inspection Report",
        ln=True
    )

    pdf.ln(10)

    pdf.set_font("Arial", size=12)

    pdf.cell(
        200,
        10,
        txt=f"Ticket ID: {ticket_id}",
        ln=True
    )

    pdf.cell(
        200,
        10,
        txt=f"Location: {location}",
        ln=True
    )

    pdf.cell(
        200,
        10,
        txt=f"PCI Score: {pci}",
        ln=True
    )

    pdf.cell(
        200,
        10,
        txt=f"Road Condition: {condition}",
        ln=True
    )

    pdf.cell(
        200,
        10,
        txt=f"Priority Level: {priority}",
        ln=True
    )

    pdf.multi_cell(
        0,
        10,
        txt=f"Municipality Action Plan: {action}"
    )

    report_path = f"reports/{ticket_id}.pdf"

    pdf.output(report_path)

    return report_path

# ==========================================
# MAIN DETECTION FUNCTION
# ==========================================

def detect_damage(
    image,
    email,
    location
):

    image_path = "temp.jpg"

    image.save(image_path)

    # ======================================
    # YOLO DETECTION
    # ======================================

    results = model(image_path)

    output_path = "output.jpg"

    results[0].save(filename=output_path)

    names = model.names

    potholes = 0
    transverse = 0
    longitudinal = 0
    alligator = 0

    # ======================================
    # COUNT DETECTIONS
    # ======================================

    for box in results[0].boxes:

        cls = int(box.cls[0])

        label = names[cls]

        print(label)

        label = label.lower()

        if "pothole" in label:

            potholes += 1

        elif "transverse" in label:

            transverse += 1

        elif "longitudinal" in label:

            longitudinal += 1

        elif "alligator" in label:

            alligator += 1

    # ======================================
    # PCI LOGIC
    # ======================================

    pci = 100

    pci -= longitudinal * 5

    pci -= transverse * 8

    pci -= potholes * 18

    pci -= alligator * 30

    pci = max(0, pci)

    # ======================================
    # ROAD CONDITION
    # ======================================

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

    # ======================================
    # PRIORITY
    # ======================================

    if pci < 20:

        priority = "Critical"

    elif pci < 40:

        priority = "High"

    elif pci < 60:

        priority = "Medium"

    else:

        priority = "Low"

    # ======================================
    # DEFECT OVERRIDE LOGIC
    # ======================================

    if alligator >= 1:

        action = "Immediate Structural Rehabilitation Required"

        priority = "Critical"

    elif potholes >= 1:

        action = "Immediate Pothole Repair Required"

        priority = "High"

    elif pci < 40:

        action = "Major Rehabilitation Required"

    elif pci < 60:

        action = "Preventive Maintenance Required"

    else:

        action = "Routine Monitoring"

    # ======================================
    # TICKET GENERATION
    # ======================================

    ticket_id = "TKT" + str(
        random.randint(1000, 9999)
    )

    date = datetime.now().strftime(
        "%d-%m-%Y %H:%M"
    )

    status = "Pending"

    # ======================================
    # SAVE TO DATABASE
    # ======================================

    c.execute("""
    INSERT INTO complaints (
        ticket_id,
        date,
        location,
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
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticket_id,
        date,
        location,
        potholes,
        transverse,
        longitudinal,
        alligator,
        pci,
        condition,
        priority,
        action,
        status
    ))

    conn.commit()

    # ======================================
    # SEND USER EMAIL
    # ======================================

    if email != "":

        send_email(
            email,
            ticket_id,
            pci,
            action
        )

    # ======================================
    # SEND CRITICAL ALERT
    # ======================================

    if priority == "Critical" or alligator >= 1:

        send_critical_alert(
            ticket_id,
            location,
            pci,
            priority,
            action
        )

    # ======================================
    # PDF REPORT
    # ======================================

    pdf_path = generate_pdf(
        ticket_id,
        location,
        pci,
        condition,
        priority,
        action
    )

    # ======================================
    # FINAL RESULT
    # ======================================

    result_text = f"""
Ticket ID: {ticket_id}

Location: {location}

Potholes Detected: {potholes}
Transverse Cracks: {transverse}
Longitudinal Cracks: {longitudinal}
Alligator Cracks: {alligator}

PCI Score: {pci}

Road Condition: {condition}

Priority Level: {priority}

Municipality Action:
{action}

Repair Status:
{status}
"""

    return (
        output_path,
        result_text,
        pdf_path
    )

# ==========================================
# TRACK COMPLAINT
# ==========================================

def track_ticket(ticket_id):

    df = pd.read_sql(
        f"SELECT * FROM complaints WHERE ticket_id='{ticket_id}'",
        conn
    )

    return df

# ==========================================
# LOAD DASHBOARD
# ==========================================

def load_dashboard():

    df = pd.read_sql(
        "SELECT * FROM complaints",
        conn
    )

    return df

# ==========================================
# UPDATE STATUS
# ==========================================

def update_status(
    ticket_id,
    new_status
):

    c.execute("""
    UPDATE complaints
    SET status=?
    WHERE ticket_id=?
    """, (
        new_status,
        ticket_id
    ))

    conn.commit()

    return f"{ticket_id} updated to {new_status}"

# ==========================================
# GRADIO UI
# ==========================================

with gr.Blocks() as demo:

    gr.Markdown(
        "# AI Smart Road Health Monitoring System"
    )

    # ======================================
    # CITIZEN PORTAL
    # ======================================

    with gr.Tab("Citizen Portal"):

        image_input = gr.Image(
            type="pil",
            sources=["upload", "webcam"],
            label="Capture Road Image"
        )

        email_input = gr.Textbox(
            label="Email Address"
        )

        location_input = gr.Textbox(
            label="Enter Road Location"
        )

        detect_button = gr.Button(
            "Analyze Road"
        )

        output_image = gr.Image(
            label="Detection Result"
        )

        result_output = gr.Textbox(
            label="Inspection Result",
            lines=18
        )

        pdf_output = gr.File(
            label="Download PDF Report"
        )

        detect_button.click(
            fn=detect_damage,
            inputs=[
                image_input,
                email_input,
                location_input
            ],
            outputs=[
                output_image,
                result_output,
                pdf_output
            ]
        )

    # ======================================
    # TRACK COMPLAINT
    # ======================================

    with gr.Tab("Track Complaint"):

        ticket_input = gr.Textbox(
            label="Enter Ticket ID"
        )

        track_button = gr.Button(
            "Track Complaint"
        )

        track_output = gr.Dataframe()

        track_button.click(
            fn=track_ticket,
            inputs=ticket_input,
            outputs=track_output
        )

    # ======================================
    # ADMIN DASHBOARD
    # ======================================

    with gr.Tab("Admin Dashboard"):

        gr.Markdown(
            "# Municipality Admin Login"
        )

        admin_username = gr.Textbox(
            label="Username"
        )

        admin_password = gr.Textbox(
            label="Password",
            type="password"
        )

        login_button = gr.Button(
            "Login"
        )

        login_status = gr.Textbox(
            label="Login Status"
        )

        admin_panel = gr.Column(
            visible=False
        )

        with admin_panel:

            gr.Markdown(
                "## Municipality Dashboard"
            )

            dashboard_button = gr.Button(
                "Load Complaints"
            )

            dashboard_output = gr.Dataframe()

            dashboard_button.click(
                fn=load_dashboard,
                outputs=dashboard_output
            )

            gr.Markdown(
                "## Update Complaint Status"
            )

            ticket_update = gr.Textbox(
                label="Ticket ID"
            )

            status_update = gr.Dropdown(
                choices=[
                    "Pending",
                    "In Progress",
                    "Resolved"
                ],
                label="Select Status"
            )

            update_button = gr.Button(
                "Update Status"
            )

            update_output = gr.Textbox(
                label="Update Result"
            )

            update_button.click(
                fn=update_status,
                inputs=[
                    ticket_update,
                    status_update
                ],
                outputs=update_output
            )

        login_button.click(
            fn=admin_login,
            inputs=[
                admin_username,
                admin_password
            ],
            outputs=[
                login_status,
                admin_panel,
                dashboard_output
            ]
        )

demo.launch()