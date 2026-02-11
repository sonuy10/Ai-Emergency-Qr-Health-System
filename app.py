from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import qrcode
import os
from datetime import datetime

# ---------------- BASIC APP SETUP ----------------
app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "app.db")
QR_FOLDER = os.path.join(BASE_DIR, "static", "qr_codes")

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
            emergency_contact TEXT,
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
        emergency_contact = request.form["emergency_contact"]

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO patient
            (name, age, blood_group, allergies, diseases, medicines, emergency_contact, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, age, blood_group, allergies,
            diseases, medicines, emergency_contact,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        patient_id = cur.lastrowid
        conn.close()

        return redirect(url_for("generate_qr", pid=patient_id))

    return render_template("register.html")

# ---------------- GENERATE QR ----------------
@app.route("/generate_qr/<int:pid>")
def generate_qr(pid):
    os.makedirs(QR_FOLDER, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM patient WHERE id=?", (pid,))
    patient = cur.fetchone()
    conn.close()

    patient_name = patient[0].replace(" ", "")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

    qr_url = request.host_url + "scan/" + str(pid)
    qr_img = qrcode.make(qr_url)

    qr_filename = f"QR_{patient_name}_{timestamp}.png"
    qr_path = os.path.join(QR_FOLDER, qr_filename)
    qr_img.save(qr_path)

    return render_template(
        "qr_generate.html",
        qr_image=f"qr_codes/{qr_filename}",
        qr_url=qr_url,
        patient_name=patient_name,
        created_time=timestamp
    )


# ---------------- SCAN QR ----------------
@app.route("/scan/<int:pid>")
def scan(pid):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM patient WHERE id = ?", (pid,))
    patient = cur.fetchone()
    conn.close()

    if patient is None:
        return "Invalid or expired QR Code"

    # -------- SIMPLE AI LOGIC (PHASE-1) --------
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

@app.route("/debug")
def debug():
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM patient")
    data = cur.fetchall()
    conn.close()
    return str(data)

