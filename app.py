from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
import qrcode
import os
from datetime import datetime
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

# ---------------- DATABASE INIT ----------------
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS patient (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            blood_group TEXT,
            allergies TEXT,
            diseases TEXT,
            medicines TEXT,
            emergency_contact_1 TEXT,
            emergency_relation_1 TEXT,
            emergency_contact_2 TEXT,
            emergency_relation_2 TEXT,
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
            (name, age, blood_group, allergies, diseases, medicines,
             emergency_contact_1, emergency_relation_1,
             emergency_contact_2, emergency_relation_2,
             created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form["name"],
            int(request.form["age"]),
            request.form["blood_group"],
            request.form["allergies"],
            request.form["diseases"],
            request.form["medicines"],
            request.form["emergency_contact_1"],
            request.form["emergency_relation_1"],
            request.form.get("emergency_contact_2"),
            request.form.get("emergency_relation_2"),
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

    width, height = qr.size

    # Proper heading space (not too much)
    header_height = 120
    new_img = Image.new("RGB", (width, height + header_height), "white")
    new_img.paste(qr, (0, header_height))

    draw = ImageDraw.Draw(new_img)

    # Use DejaVu font (works on Render)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
    except:
        font = ImageFont.load_default()

    line1 = "EMERGENCY MEDICAL QR"
    line2 = "SCAN IMMEDIATELY"

    # Center align text
    w1 = draw.textlength(line1, font=font)
    w2 = draw.textlength(line2, font=font)

    x1 = (width - w1) / 2
    x2 = (width - w2) / 2

    # Reduced gap between lines
    draw.text((x1, 20), line1, fill="red", font=font)
    draw.text((x2, 65), line2, fill="red", font=font)

    filename = f"Emergency_QR_{patient_name}.png"
    file_path = os.path.join(QR_FOLDER, filename)
    new_img.save(file_path)

    return render_template(
        "qr_generate.html",
        qr_image=filename,
        qr_url=qr_url,
        patient_name=patient_name,
        created_time=created_time
    )


# ---------------- DOWNLOAD QR ----------------
@app.route("/download/<filename>")
def download_file(filename):
    path = os.path.join(QR_FOLDER, filename)
    return send_file(path, as_attachment=True)

# ---------------- EMAIL FUNCTION (BREVO API) ----------------
def send_qr_email(to_email, filename):

    if not BREVO_API_KEY:
        print("Brevo API key missing")
        return "Not Configured"

    try:
        path = os.path.join(QR_FOLDER, filename)

        with open(path, "rb") as f:
            encoded_file = base64.b64encode(f.read()).decode()

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
            "htmlContent": "<p>Your Emergency Medical QR is attached.</p>",
            "attachment": [{
                "content": encoded_file,
                "name": filename
            }]
        }

        response = requests.post(url, json=payload, headers=headers)

        print("Brevo Response:", response.status_code, response.text)

        if response.status_code == 201:
            return "Success"
        else:
            return "Failed"

    except Exception as e:
        print("EMAIL ERROR:", e)
        return "Failed"

# ---------------- EMAIL ROUTE ----------------
@app.route("/send_email/<filename>", methods=["POST"])
def send_email(filename):
    email = request.form["email"]
    result = send_qr_email(email, filename)
    print("Email status:", result)
    return redirect(request.referrer)

# ---------------- SCAN QR ----------------
@app.route("/scan/<int:pid>")
def scan(pid):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM patient WHERE id=?", (pid,))
    patient = cur.fetchone()
    conn.close()

    if patient is None:
        return "Invalid or expired QR Code"

    age = patient[2]
    diseases = (patient[5] or "").lower()

    if age >= 60 or "heart" in diseases or "diabetes" in diseases:
        risk = "HIGH"
        triage = "RED"
    elif age >= 40:
        risk = "MEDIUM"
        triage = "YELLOW"
    else:
        risk = "LOW"
        triage = "GREEN"

    return render_template(
        "emergency_view.html",
        patient=patient,
        risk=risk,
        triage=triage
    )

# ---------------- FIND HOSPITAL ----------------
@app.route("/find_hospital")
def find_hospital():
    return redirect("https://www.google.com/maps/search/hospital+near+me/")

# ---------------- RUN APP ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


