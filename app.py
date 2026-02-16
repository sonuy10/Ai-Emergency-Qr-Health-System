from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
import qrcode
import os
from datetime import datetime, date
import pytz
from PIL import Image, ImageDraw, ImageFont
import requests
import base64

# ---------------- BASIC PATH SETUP ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "app.db")
QR_FOLDER = os.path.join(BASE_DIR, "static")

app = Flask(__name__)

# ---------------- BREVO API KEY ----------------
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")

# ---------------- IST TIME FUNCTION ----------------
def get_ist_time():
    ist = pytz.timezone("Asia/Kolkata")
    return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

# ---------------- CALCULATE AGE FROM DOB ----------------
def calculate_age(dob):
    dob = datetime.strptime(dob, "%Y-%m-%d").date()
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

# ---------------- DATABASE INIT ----------------
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS patient (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            dob TEXT,
            blood_group TEXT,
            allergies TEXT,
            diseases TEXT,
            medicines TEXT,
            emergency_contact_1 TEXT,
            emergency_relation_1 TEXT,
            emergency_contact_2 TEXT,
            emergency_relation_2 TEXT,
            edit_password TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- HOME ----------------
@app.route("/")
def index():
    return render_template("index.html")

# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO patient
            (name, dob, blood_group, allergies, diseases, medicines,
            emergency_contact_1, emergency_relation_1,
            emergency_contact_2, emergency_relation_2,
            edit_password, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (

            request.form["name"],
            request.form["dob"],
            request.form["blood_group"],
            request.form["allergies"],
            request.form["diseases"],
            request.form["medicines"],
            request.form["emergency_contact_1"],
            request.form["emergency_relation_1"],
            request.form.get("emergency_contact_2"),
            request.form.get("emergency_relation_2"),
            request.form["edit_password"],
            get_ist_time()

        ))

        conn.commit()
        patient_id = cur.lastrowid
        conn.close()

        return redirect(url_for("generate_qr", pid=patient_id))

    return render_template("register.html")

# ---------------- GENERATE QR ----------------
@app.route("/generate_qr/<int:pid>")
def generate_qr(pid):

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM patient WHERE id=?", (pid,))
    patient = cur.fetchone()
    conn.close()

    if patient is None:
        return "Patient not found"

    patient_name = patient[0].replace(" ", "_")
    created_time = get_ist_time()

    qr_url = request.host_url + "scan/" + str(pid)
    qr = qrcode.make(qr_url).convert("RGB")

    qr_width, qr_height = qr.size

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 42)
    except:
        font = ImageFont.load_default()

    line1 = "EMERGENCY MEDICAL QR"
    line2 = "SCAN IMMEDIATELY"

    dummy = Image.new("RGB", (1, 1))
    draw_dummy = ImageDraw.Draw(dummy)

    text_width1 = draw_dummy.textlength(line1, font=font)
    text_width2 = draw_dummy.textlength(line2, font=font)

    final_width = int(max(qr_width, text_width1, text_width2) + 40)
    header_height = 130

    img = Image.new("RGB", (final_width, qr_height + header_height), "white")
    draw = ImageDraw.Draw(img)

    x1 = (final_width - text_width1) / 2
    x2 = (final_width - text_width2) / 2

    draw.text((x1, 25), line1, fill="red", font=font)
    draw.text((x2, 70), line2, fill="red", font=font)

    qr_x = (final_width - qr_width) // 2
    img.paste(qr, (qr_x, header_height))

    filename = f"Emergency_QR_{patient_name}.png"
    file_path = os.path.join(QR_FOLDER, filename)

    img.save(file_path)

    return render_template(
        "qr_generate.html",
        qr_image=filename,
        qr_url=qr_url,
        patient_name=patient_name,
        created_time=created_time
    )

# ---------------- DOWNLOAD ----------------
@app.route("/download/<filename>")
def download_file(filename):
    path = os.path.join(QR_FOLDER, filename)
    return send_file(path, as_attachment=True)

# ---------------- SEND EMAIL ----------------
def send_qr_email(to_email, filename):

    if not BREVO_API_KEY:
        return "Not Configured"

    path = os.path.join(QR_FOLDER, filename)

    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()

    url = "https://api.brevo.com/v3/smtp/email"

    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }

    payload = {
        "sender": {
            "name": "AI Emergency QR",
            "email": "sonuyadava0506@gmail.com"
        },
        "to": [{"email": to_email}],
        "subject": "Emergency Medical QR Code",
        "htmlContent": "<p>Your QR is attached</p>",
        "attachment": [{"content": encoded, "name": filename}]
    }

    requests.post(url, json=payload, headers=headers)

# ---------------- EMAIL ROUTE ----------------
@app.route("/send_email/<filename>", methods=["POST"])
def send_email(filename):

    email = request.form["email"]
    send_qr_email(email, filename)

    return redirect(request.referrer)

# ---------------- SCAN ----------------
@app.route("/scan/<int:pid>")
def scan(pid):

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT * FROM patient WHERE id=?", (pid,))
    patient = cur.fetchone()

    conn.close()

    age = calculate_age(patient[2])

    return render_template("emergency_view.html", patient=patient, age=age)

# ---------------- EDIT VERIFY ----------------
@app.route("/verify/<int:pid>", methods=["POST"])
def verify(pid):

    password = request.form["password"]

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT edit_password FROM patient WHERE id=?", (pid,))
    real = cur.fetchone()[0]

    conn.close()

    if password == real:
        return redirect("/edit/" + str(pid))
    else:
        return "Wrong Password"

# ---------------- EDIT ----------------
@app.route("/edit/<int:pid>", methods=["GET", "POST"])
def edit(pid):

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    if request.method == "POST":

        cur.execute("""
            UPDATE patient SET
            name=?,
            dob=?,
            blood_group=?,
            allergies=?,
            diseases=?,
            medicines=?,
            emergency_contact_1=?,
            emergency_relation_1=?,
            emergency_contact_2=?,
            emergency_relation_2=?
            WHERE id=?
        """, (

            request.form["name"],
            request.form["dob"],
            request.form["blood_group"],
            request.form["allergies"],
            request.form["diseases"],
            request.form["medicines"],
            request.form["emergency_contact_1"],
            request.form["emergency_relation_1"],
            request.form.get("emergency_contact_2"),
            request.form.get("emergency_relation_2"),
            pid

        ))

        conn.commit()
        conn.close()

        return redirect("/scan/" + str(pid))

    cur.execute("SELECT * FROM patient WHERE id=?", (pid,))
    patient = cur.fetchone()

    conn.close()

    return render_template("edit_form.html", patient=patient)

# ---------------- RUN ----------------
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(host="0.0.0.0", port=port)
