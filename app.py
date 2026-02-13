from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import qrcode
import os
from datetime import datetime
import pytz   # IST support

# ---------------- BASIC PATH SETUP ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "database", "app.db")
QR_TEMP_PATH = os.path.join(BASE_DIR, "static", "temp_qr.png")

app = Flask(__name__)

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
        name = request.form["name"]
        age = int(request.form["age"])
        blood_group = request.form["blood_group"]
        allergies = request.form["allergies"]
        diseases = request.form["diseases"]
        medicines = request.form["medicines"]

        emergency_contact_1 = request.form["emergency_contact_1"]
        emergency_relation_1 = request.form["emergency_relation_1"]

        emergency_contact_2 = request.form.get("emergency_contact_2")
        emergency_relation_2 = request.form.get("emergency_relation_2")

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
            name, age, blood_group, allergies, diseases, medicines,
            emergency_contact_1, emergency_relation_1,
            emergency_contact_2, emergency_relation_2,
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

    patient_name = patient[0]
    created_time = get_ist_time()

    qr_url = request.host_url + "scan/" + str(pid)

    qr_img = qrcode.make(qr_url)
    qr_img.save(QR_TEMP_PATH)

    return render_template(
        "qr_generate.html",
        qr_image="temp_qr.png",
        qr_url=qr_url,
        patient_name=patient_name,
        created_time=created_time
    )

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

    # ---------- SIMPLE AI LOGIC ----------
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

# ---------------- DEBUG ----------------
@app.route("/debug")
def debug():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM patient")
    data = cur.fetchall()
    conn.close()
    return str(data)

# ---------------- RUN APP ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
