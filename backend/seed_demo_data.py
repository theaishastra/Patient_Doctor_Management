"""
Seed demo data via the running FastAPI server's HTTP API.

Creates:
  - 1 admin (registered as patient via /api/auth/register, then promoted
    to role='admin' directly in the database, since the public register
    endpoint only allows 'doctor'/'patient')
  - 2 doctors
  - 3 patients
  - Assignments: doctor1 -> patient1, doctor1 -> patient2, doctor2 -> patient3

Requires the backend server to be running at BASE_URL (default
http://127.0.0.1:8000). Run with the project's venv:

    cd backend
    .\venv\Scripts\python.exe seed_demo_data.py
"""

import sys
import httpx
from database import supabase_admin

BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PASSWORD = "Password123!"

ADMIN = {"full_name": "Portal Administrator", "email": "admin@medvitals.com"}

DOCTORS = [
    {"full_name": "Dr. Aditi Sharma", "email": "doctor1@medvitals.com"},
    {"full_name": "Dr. Rohan Mehta", "email": "doctor2@medvitals.com"},
]

PATIENTS = [
    {"full_name": "Asha Verma", "email": "patient1@medvitals.com"},
    {"full_name": "Karan Patel", "email": "patient2@medvitals.com"},
    {"full_name": "Neha Gupta", "email": "patient3@medvitals.com"},
]


def register(client: httpx.Client, full_name: str, email: str, role: str):
    resp = client.post("/api/auth/register", json={
        "full_name": full_name,
        "email": email,
        "password": DEFAULT_PASSWORD,
        "role": role
    })
    if resp.status_code == 200:
        print(f"  Registered {role}: {email}")
        return resp.json()["user_id"]

    detail = resp.json().get("detail", resp.text)
    if "already registered" in detail.lower() or "already exists" in detail.lower():
        print(f"  Already exists, skipping: {email}")
        existing = supabase_admin.table("profiles").select("id").eq("email", email).execute()
        if existing.data:
            return existing.data[0]["id"]
        return None

    print(f"  FAILED to register {email}: {detail}")
    return None


def login(client: httpx.Client, email: str, password: str):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        print(f"  FAILED to login {email}: {resp.json().get('detail', resp.text)}")
        return None
    return resp.json()


def create_assignment(client: httpx.Client, token: str, doctor_id: str, patient_id: str):
    resp = client.post(
        "/api/admin/assignments",
        json={"doctor_id": doctor_id, "patient_id": patient_id},
        headers={"Authorization": f"Bearer {token}"}
    )
    if resp.status_code == 200:
        print(f"  Assigned doctor {doctor_id} -> patient {patient_id}")
    else:
        detail = resp.json().get("detail", resp.text)
        print(f"  FAILED to assign doctor {doctor_id} -> patient {patient_id}: {detail}")


def main():
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        try:
            client.get("/docs")
        except httpx.ConnectError:
            print(f"ERROR: cannot reach backend server at {BASE_URL}. Start it first with 'python main.py'.")
            sys.exit(1)

        print("\n1. Registering admin...")
        admin_id = register(client, ADMIN["full_name"], ADMIN["email"], "patient")
        if admin_id:
            supabase_admin.table("profiles").update({"role": "admin"}).eq("id", admin_id).execute()
            # Remove leftover patient-extension row created by the register trigger
            supabase_admin.table("patients").delete().eq("id", admin_id).execute()
            print(f"  Promoted {ADMIN['email']} to role=admin")

        print("\n2. Registering doctors...")
        doctor_ids = []
        for doc in DOCTORS:
            doctor_ids.append(register(client, doc["full_name"], doc["email"], "doctor"))

        print("\n3. Registering patients...")
        patient_ids = []
        for pat in PATIENTS:
            patient_ids.append(register(client, pat["full_name"], pat["email"], "patient"))

        print("\n4. Logging in as admin...")
        admin_session = login(client, ADMIN["email"], DEFAULT_PASSWORD)
        if not admin_session or admin_session["user"]["role"] != "admin":
            print("  ERROR: admin login failed or role not promoted. Aborting assignments.")
            sys.exit(1)
        admin_token = admin_session["access_token"]
        print(f"  Logged in as admin: {admin_session['user']['email']}")

        print("\n5. Creating assignments (doctor1 -> patient1, patient2; doctor2 -> patient3)...")
        if doctor_ids[0] and patient_ids[0]:
            create_assignment(client, admin_token, doctor_ids[0], patient_ids[0])
        if doctor_ids[0] and patient_ids[1]:
            create_assignment(client, admin_token, doctor_ids[0], patient_ids[1])
        if doctor_ids[1] and patient_ids[2]:
            create_assignment(client, admin_token, doctor_ids[1], patient_ids[2])

    print("\n" + "=" * 60)
    print("DEMO CREDENTIALS (all use password: %s)" % DEFAULT_PASSWORD)
    print("=" * 60)
    print(f"  Admin:    {ADMIN['email']}")
    for doc in DOCTORS:
        print(f"  Doctor:   {doc['email']}")
    for pat in PATIENTS:
        print(f"  Patient:  {pat['email']}")
    print("=" * 60)
    print("Doctor 1 (doctor1@medvitals.com) is assigned to Patient 1 & Patient 2")
    print("Doctor 2 (doctor2@medvitals.com) is assigned to Patient 3")


if __name__ == "__main__":
    main()
