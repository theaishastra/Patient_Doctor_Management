import mimetypes
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from database import supabase_admin
from routers.auth import require_role, log_activity
import chat_service

router = APIRouter(prefix="/api/doctor", tags=["doctor"])

# Check if user is a doctor
doctor_dependency = Depends(require_role(["doctor"]))

# Pydantic Schemas
class TreatmentCreateSchema(BaseModel):
    patient_id: str
    diagnosis: str
    treatment_plan: str
    suggested_medicines: str
    notes: Optional[str] = None

class TreatmentUpdateSchema(BaseModel):
    diagnosis: Optional[str] = None
    treatment_plan: Optional[str] = None
    suggested_medicines: Optional[str] = None
    notes: Optional[str] = None

class DoctorProfileUpdateSchema(BaseModel):
    specialization: Optional[str] = None
    license_number: Optional[str] = None
    contact_number: Optional[str] = None
    bio: Optional[str] = None

class ChangePasswordSchema(BaseModel):
    current_password: str
    new_password: str

# Helper to check doctor-patient assignment
def check_assignment(doctor_id: str, patient_id: str):
    res = supabase_admin.table("assignments").select("id").eq("doctor_id", doctor_id).eq("patient_id", patient_id).execute()
    return len(res.data) > 0

# Endpoints
@router.get("/patients")
async def list_assigned_patients(doctor_profile = Depends(require_role(["doctor"]))):
    try:
        # Fetch patients assigned to this doctor
        res = supabase_admin.table("assignments").select(
            "*, patient:patients(*, profiles(full_name, email))"
        ).eq("doctor_id", doctor_profile["id"]).execute()
        
        flat_patients = []
        for item in res.data:
            patient = item.get("patient", {})
            profile = patient.get("profiles", {}) if patient else {}
            if patient:
                flat_patients.append({
                    "assignment_id": item["id"],
                    "id": patient["id"],
                    "full_name": profile.get("full_name", "Unknown"),
                    "email": profile.get("email", ""),
                    "date_of_birth": patient.get("date_of_birth"),
                    "gender": patient.get("gender"),
                    "blood_group": patient.get("blood_group"),
                    "contact_number": patient.get("contact_number"),
                    "emergency_contact": patient.get("emergency_contact"),
                    "assigned_at": item["assigned_at"]
                })
        return flat_patients
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/patients/{patient_id}/history")
async def get_patient_history(patient_id: str, doctor_profile = Depends(require_role(["doctor"]))):
    # Verify assignment
    if not check_assignment(doctor_profile["id"], patient_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You are not assigned to this patient."
        )

    try:
        # Fetch patient's basic info
        patient_res = supabase_admin.table("patients").select("*, profiles(full_name, email)").eq("id", patient_id).execute()
        if not patient_res.data:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        patient_data = patient_res.data[0]
        profile = patient_data.get("profiles", {})
        patient_info = {
            "id": patient_data["id"],
            "full_name": profile.get("full_name", ""),
            "email": profile.get("email", ""),
            "date_of_birth": patient_data.get("date_of_birth"),
            "gender": patient_data.get("gender"),
            "blood_group": patient_data.get("blood_group"),
            "contact_number": patient_data.get("contact_number"),
            "emergency_contact": patient_data.get("emergency_contact")
        }

        # Fetch all treatments for this patient (including name of the diagnosing doctor)
        treatments_res = supabase_admin.table("treatments").select(
            "*, doctor:doctors(profiles(full_name))"
        ).eq("patient_id", patient_id).order("created_at", desc=True).execute()

        flat_treatments = []
        for treat in treatments_res.data:
            doc_profile = treat.get("doctor", {}).get("profiles", {}) if treat.get("doctor") else {}
            flat_treatments.append({
                "id": treat["id"],
                "doctor_id": treat["doctor_id"],
                "doctor_name": doc_profile.get("full_name", "Unknown Doctor"),
                "diagnosis": treat["diagnosis"],
                "treatment_plan": treat["treatment_plan"],
                "suggested_medicines": treat["suggested_medicines"],
                "notes": treat["notes"],
                "created_at": treat["created_at"]
            })

        # Fetch patient uploaded documents
        docs_res = supabase_admin.table("medical_documents").select("*").eq("patient_id", patient_id).order("uploaded_at", desc=True).execute()

        return {
            "patient": patient_info,
            "treatments": flat_treatments,
            "documents": docs_res.data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/documents/{doc_id}/view")
async def view_patient_document(doc_id: str, doctor_profile = Depends(require_role(["doctor"]))):
    bucket_name = "medical-documents"
    try:
        doc_res = supabase_admin.table("medical_documents").select("*").eq("id", doc_id).execute()
        if not doc_res.data:
            raise HTTPException(status_code=404, detail="Document not found")

        document = doc_res.data[0]

        # Verify the doctor is assigned to this patient
        if not check_assignment(doctor_profile["id"], document["patient_id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You are not assigned to this patient."
            )

        file_bytes = supabase_admin.storage.from_(bucket_name).download(document["file_path"])
        content_type, _ = mimetypes.guess_type(document["file_name"])
        return Response(content=file_bytes, media_type=content_type or "application/octet-stream")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load document: {str(e)}"
        )

@router.post("/treatments")
async def create_treatment(data: TreatmentCreateSchema, doctor_profile = Depends(require_role(["doctor"]))):
    # Verify assignment
    if not check_assignment(doctor_profile["id"], data.patient_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You can only prescribe treatments to assigned patients."
        )

    try:
        # Insert treatment
        res = supabase_admin.table("treatments").insert({
            "patient_id": data.patient_id,
            "doctor_id": doctor_profile["id"],
            "diagnosis": data.diagnosis,
            "treatment_plan": data.treatment_plan,
            "suggested_medicines": data.suggested_medicines,
            "notes": data.notes
        }).execute()

        # Log activity
        log_activity(
            user_id=doctor_profile["id"],
            user_name=doctor_profile["full_name"],
            role="doctor",
            action="Add Treatment",
            details=f"Added treatment/diagnosis for Patient ID: {data.patient_id}"
        )

        return {"message": "Treatment recorded successfully", "data": res.data[0]}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.put("/treatments/{treatment_id}")
async def update_treatment(treatment_id: str, data: TreatmentUpdateSchema, doctor_profile = Depends(require_role(["doctor"]))):
    try:
        # Check if treatment exists and was created by this doctor
        check_res = supabase_admin.table("treatments").select("doctor_id, patient_id").eq("id", treatment_id).execute()
        if not check_res.data:
            raise HTTPException(status_code=404, detail="Treatment record not found")
        
        treatment_record = check_res.data[0]
        if treatment_record["doctor_id"] != doctor_profile["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only edit treatments you recorded."
            )

        # Update treatment
        update_data = {}
        if data.diagnosis is not None:
            update_data["diagnosis"] = data.diagnosis
        if data.treatment_plan is not None:
            update_data["treatment_plan"] = data.treatment_plan
        if data.suggested_medicines is not None:
            update_data["suggested_medicines"] = data.suggested_medicines
        if data.notes is not None:
            update_data["notes"] = data.notes

        if not update_data:
            return {"message": "No changes to update"}

        res = supabase_admin.table("treatments").update(update_data).eq("id", treatment_id).execute()

        # Log activity
        log_activity(
            user_id=doctor_profile["id"],
            user_name=doctor_profile["full_name"],
            role="doctor",
            action="Update Treatment",
            details=f"Updated treatment ID: {treatment_id} for Patient ID: {treatment_record['patient_id']}"
        )

        return {"message": "Treatment updated successfully", "data": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/profile")
async def get_doctor_profile(doctor_profile = Depends(require_role(["doctor"]))):
    try:
        res = supabase_admin.table("doctors").select("*, profiles(full_name, email)").eq("id", doctor_profile["id"]).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Doctor profile details not found")
        doc = res.data[0]
        profile = doc.get("profiles", {})
        return {
            "id": doc["id"],
            "full_name": profile.get("full_name", ""),
            "email": profile.get("email", ""),
            "specialization": doc.get("specialization"),
            "license_number": doc.get("license_number"),
            "contact_number": doc.get("contact_number"),
            "bio": doc.get("bio")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.put("/profile")
async def update_own_profile(data: DoctorProfileUpdateSchema, doctor_profile = Depends(require_role(["doctor"]))):
    try:
        doc_id = doctor_profile["id"]
        update_data = {}
        if data.specialization is not None:
            update_data["specialization"] = data.specialization
        if data.license_number is not None:
            update_data["license_number"] = data.license_number
        if data.contact_number is not None:
            update_data["contact_number"] = data.contact_number
        if data.bio is not None:
            update_data["bio"] = data.bio

        if update_data:
            supabase_admin.table("doctors").update(update_data).eq("id", doc_id).execute()

        log_activity(
            user_id=doc_id,
            user_name=doctor_profile["full_name"],
            role="doctor",
            action="Update Profile",
            details="Doctor updated professional profile details"
        )
        return {"message": "Profile updated successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ==========================================
# CHAT
# ==========================================
@router.get("/chats")
async def list_chats(doctor_profile = Depends(require_role(["doctor"]))):
    try:
        res = supabase_admin.table("assignments").select(
            "*, patient:patients(*, profiles(full_name))"
        ).eq("doctor_id", doctor_profile["id"]).execute()

        chats = []
        for item in res.data:
            patient = item.get("patient", {})
            pat_profile = patient.get("profiles", {}) if patient else {}

            last_msg_res = supabase_admin.table("chat_messages").select(
                "content, message_type, created_at"
            ).eq("assignment_id", item["id"]).order("created_at", desc=True).limit(1).execute()
            last_msg = last_msg_res.data[0] if last_msg_res.data else None

            chats.append({
                "assignment_id": item["id"],
                "patient_id": item["patient_id"],
                "patient_name": pat_profile.get("full_name", "Unknown"),
                "last_message_preview": (last_msg["content"] if last_msg["message_type"] == "text" else f"[{last_msg['message_type']}]") if last_msg else None,
                "last_message_at": last_msg["created_at"] if last_msg else None,
            })
        return chats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/chats/{assignment_id}/messages")
async def get_chat_messages(assignment_id: str, doctor_profile = Depends(require_role(["doctor"]))):
    chat_service.verify_chat_access(assignment_id, doctor_profile)
    return chat_service.list_chat_messages(assignment_id)

@router.post("/chats/{assignment_id}/messages")
async def send_chat_message(
    assignment_id: str,
    content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    doctor_profile = Depends(require_role(["doctor"]))
):
    chat_service.verify_chat_access(assignment_id, doctor_profile)
    message = await chat_service.create_chat_message(
        assignment_id, doctor_profile["id"], "doctor", doctor_profile["full_name"], content, file
    )
    log_activity(
        user_id=doctor_profile["id"],
        user_name=doctor_profile["full_name"],
        role="doctor",
        action="Send Chat Message",
        details=f"Sent a {message['message_type']} message in chat {assignment_id}"
    )
    return message

@router.get("/chats/messages/{message_id}/media")
async def get_chat_message_media(message_id: str, doctor_profile = Depends(require_role(["doctor"]))):
    file_bytes, content_type, file_name = chat_service.get_chat_media(message_id, doctor_profile)
    return Response(content=file_bytes, media_type=content_type)

# ==========================================
# CREDENTIALS
# ==========================================
@router.post("/change-password")
async def change_password(data: ChangePasswordSchema, doctor_profile = Depends(require_role(["doctor"]))):
    return chat_service.change_own_password(doctor_profile, data.current_password, data.new_password)
