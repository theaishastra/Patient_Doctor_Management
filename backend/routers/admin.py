from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from database import supabase_admin
from routers.auth import require_role, log_activity
import chat_service

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Check if user is admin for all endpoints in this router
admin_dependency = Depends(require_role(["admin"]))

# Pydantic Schemas
class DoctorUpdateSchema(BaseModel):
    full_name: Optional[str] = None
    specialization: Optional[str] = None
    license_number: Optional[str] = None
    contact_number: Optional[str] = None
    bio: Optional[str] = None

class PatientUpdateSchema(BaseModel):
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None # YYYY-MM-DD
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    contact_number: Optional[str] = None
    emergency_contact: Optional[str] = None

class AssignmentCreateSchema(BaseModel):
    doctor_id: str
    patient_id: str

class AdminResetPasswordSchema(BaseModel):
    new_password: str

class CreateUserSchema(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str  # 'doctor' or 'patient'

# Endpoints
@router.get("/dashboard-stats", dependencies=[admin_dependency])
async def get_dashboard_stats():
    try:
        # Get count of patients
        patients_res = supabase_admin.table("patients").select("id", count="exact").execute()
        patients_count = patients_res.count if patients_res.count is not None else len(patients_res.data)

        # Get count of doctors
        doctors_res = supabase_admin.table("doctors").select("id", count="exact").execute()
        doctors_count = doctors_res.count if doctors_res.count is not None else len(doctors_res.data)

        # Get count of treatments
        treatments_res = supabase_admin.table("treatments").select("id", count="exact").execute()
        treatments_count = treatments_res.count if treatments_res.count is not None else len(treatments_res.data)

        # Get recent activity logs (limit to 10)
        logs_res = supabase_admin.table("activity_logs").select("*").order("created_at", desc=True).limit(10).execute()

        return {
            "stats": {
                "doctors": doctors_count,
                "patients": patients_count,
                "treatments": treatments_count
            },
            "recent_logs": logs_res.data
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

@router.get("/doctors", dependencies=[admin_dependency])
async def list_doctors():
    try:
        # Fetch profiles that are doctors and join details from public.doctors
        # We can perform a join using supabase-py select("*", "profiles(*)")
        res = supabase_admin.table("doctors").select("*, profiles(full_name, email)").execute()
        
        # Flatten the response for easier frontend usage
        flat_doctors = []
        for doc in res.data:
            profile = doc.get("profiles", {})
            flat_doctors.append({
                "id": doc["id"],
                "full_name": profile.get("full_name", "Unknown"),
                "email": profile.get("email", ""),
                "specialization": doc.get("specialization"),
                "license_number": doc.get("license_number"),
                "contact_number": doc.get("contact_number"),
                "bio": doc.get("bio"),
                "is_active": doc.get("is_active", True),
                "created_at": doc.get("created_at")
            })
        return flat_doctors
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.put("/doctors/{doctor_id}", dependencies=[admin_dependency])
async def update_doctor(doctor_id: str, data: DoctorUpdateSchema, admin_profile = Depends(require_role(["admin"]))):
    try:
        # 1. Update full_name in profiles if provided
        if data.full_name is not None:
            supabase_admin.table("profiles").update({"full_name": data.full_name}).eq("id", doctor_id).execute()

        # 2. Update doctors table
        doctor_update = {}
        if data.specialization is not None:
            doctor_update["specialization"] = data.specialization
        if data.license_number is not None:
            doctor_update["license_number"] = data.license_number
        if data.contact_number is not None:
            doctor_update["contact_number"] = data.contact_number
        if data.bio is not None:
            doctor_update["bio"] = data.bio

        if doctor_update:
            supabase_admin.table("doctors").update(doctor_update).eq("id", doctor_id).execute()

        log_activity(
            user_id=admin_profile["id"],
            user_name=admin_profile["full_name"],
            role="admin",
            action="Update Doctor Profile",
            details=f"Updated doctor profile for ID: {doctor_id}"
        )
        return {"message": "Doctor profile updated successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/patients", dependencies=[admin_dependency])
async def list_patients():
    try:
        res = supabase_admin.table("patients").select("*, profiles(full_name, email)").execute()
        
        flat_patients = []
        for pat in res.data:
            profile = pat.get("profiles", {})
            flat_patients.append({
                "id": pat["id"],
                "full_name": profile.get("full_name", "Unknown"),
                "email": profile.get("email", ""),
                "date_of_birth": pat.get("date_of_birth"),
                "gender": pat.get("gender"),
                "blood_group": pat.get("blood_group"),
                "contact_number": pat.get("contact_number"),
                "emergency_contact": pat.get("emergency_contact"),
                "created_at": pat.get("created_at")
            })
        return flat_patients
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.put("/patients/{patient_id}", dependencies=[admin_dependency])
async def update_patient(patient_id: str, data: PatientUpdateSchema, admin_profile = Depends(require_role(["admin"]))):
    try:
        # 1. Update full_name in profiles if provided
        if data.full_name is not None:
            supabase_admin.table("profiles").update({"full_name": data.full_name}).eq("id", patient_id).execute()

        # 2. Update patients table
        patient_update = {}
        if data.date_of_birth is not None:
            patient_update["date_of_birth"] = data.date_of_birth if data.date_of_birth != "" else None
        if data.gender is not None:
            patient_update["gender"] = data.gender
        if data.blood_group is not None:
            patient_update["blood_group"] = data.blood_group
        if data.contact_number is not None:
            patient_update["contact_number"] = data.contact_number
        if data.emergency_contact is not None:
            patient_update["emergency_contact"] = data.emergency_contact

        if patient_update:
            supabase_admin.table("patients").update(patient_update).eq("id", patient_id).execute()

        log_activity(
            user_id=admin_profile["id"],
            user_name=admin_profile["full_name"],
            role="admin",
            action="Update Patient Profile",
            details=f"Updated patient profile for ID: {patient_id}"
        )
        return {"message": "Patient profile updated successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/assignments", dependencies=[admin_dependency])
async def list_assignments():
    try:
        res = supabase_admin.table("assignments").select("*, doctor:doctors(profiles(full_name)), patient:patients(profiles(full_name))").execute()
        
        flat_assignments = []
        for item in res.data:
            doc_profile = item.get("doctor", {}).get("profiles", {}) if item.get("doctor") else {}
            pat_profile = item.get("patient", {}).get("profiles", {}) if item.get("patient") else {}
            flat_assignments.append({
                "id": item["id"],
                "doctor_id": item["doctor_id"],
                "doctor_name": doc_profile.get("full_name", "Unknown Doctor"),
                "patient_id": item["patient_id"],
                "patient_name": pat_profile.get("full_name", "Unknown Patient"),
                "assigned_at": item["assigned_at"]
            })
        return flat_assignments
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/assignments", dependencies=[admin_dependency])
async def create_assignment(data: AssignmentCreateSchema, admin_profile = Depends(require_role(["admin"]))):
    try:
        # Create assignment
        res = supabase_admin.table("assignments").insert({
            "doctor_id": data.doctor_id,
            "patient_id": data.patient_id
        }).execute()
        
        # Log assignment activity
        log_activity(
            user_id=admin_profile["id"],
            user_name=admin_profile["full_name"],
            role="admin",
            action="Assign Patient",
            details=f"Assigned Patient ID {data.patient_id} to Doctor ID {data.doctor_id}"
        )
        return {"message": "Patient assigned to doctor successfully", "data": res.data[0]}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to assign. Assignment might already exist. Error: {str(e)}"
        )

@router.delete("/assignments/{assignment_id}", dependencies=[admin_dependency])
async def delete_assignment(assignment_id: str, admin_profile = Depends(require_role(["admin"]))):
    try:
        res = supabase_admin.table("assignments").delete().eq("id", assignment_id).execute()
        
        log_activity(
            user_id=admin_profile["id"],
            user_name=admin_profile["full_name"],
            role="admin",
            action="Remove Assignment",
            details=f"Removed assignment ID {assignment_id}"
        )
        return {"message": "Assignment removed successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/activity-logs", dependencies=[admin_dependency])
async def list_activity_logs():
    try:
        res = supabase_admin.table("activity_logs").select("*").order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ==========================================
# CHAT MONITORING (GOD MODE)
# ==========================================
@router.get("/chats/{assignment_id}/messages", dependencies=[admin_dependency])
async def get_chat_messages(assignment_id: str, admin_profile = Depends(require_role(["admin"]))):
    chat_service.verify_chat_access(assignment_id, admin_profile)
    return chat_service.list_chat_messages(assignment_id)

@router.post("/chats/{assignment_id}/messages")
async def send_chat_message(
    assignment_id: str,
    content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    admin_profile = Depends(require_role(["admin"]))
):
    chat_service.verify_chat_access(assignment_id, admin_profile)
    message = await chat_service.create_chat_message(
        assignment_id, admin_profile["id"], "admin", admin_profile["full_name"], content, file
    )
    log_activity(
        user_id=admin_profile["id"],
        user_name=admin_profile["full_name"],
        role="admin",
        action="Send Chat Message",
        details=f"Sent a {message['message_type']} message in chat {assignment_id}"
    )
    return message

@router.get("/chats/messages/{message_id}/media", dependencies=[admin_dependency])
async def get_chat_message_media(message_id: str, admin_profile = Depends(require_role(["admin"]))):
    file_bytes, content_type, file_name = chat_service.get_chat_media(message_id, admin_profile)
    return Response(content=file_bytes, media_type=content_type)

@router.get("/chats/{assignment_id}/export", dependencies=[admin_dependency])
async def export_chat(assignment_id: str, admin_profile = Depends(require_role(["admin"]))):
    chat_service.verify_chat_access(assignment_id, admin_profile)
    buffer = chat_service.build_chat_zip(assignment_id)

    log_activity(
        user_id=admin_profile["id"],
        user_name=admin_profile["full_name"],
        role="admin",
        action="Export Chat History",
        details=f"Exported chat history for assignment {assignment_id}"
    )

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="chat_{assignment_id}.zip"'}
    )

# ==========================================
# CREDENTIALS MANAGEMENT
# ==========================================
@router.post("/users/{user_id}/reset-password", dependencies=[admin_dependency])
async def reset_user_password(user_id: str, data: AdminResetPasswordSchema, admin_profile = Depends(require_role(["admin"]))):
    try:
        profile_res = supabase_admin.table("profiles").select("*").eq("id", user_id).execute()
        if not profile_res.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        target_profile = profile_res.data[0]
        if target_profile["role"] not in ("doctor", "patient"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only reset passwords for doctors and patients")

        supabase_admin.auth.admin.update_user_by_id(user_id, {"password": data.new_password})

        log_activity(
            user_id=admin_profile["id"],
            user_name=admin_profile["full_name"],
            role="admin",
            action="Admin Reset Password",
            details=f"Reset password for {target_profile['role']} {target_profile['full_name']} (ID: {user_id})"
        )

        return {"message": "Password reset successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/users", dependencies=[admin_dependency])
async def create_user(data: CreateUserSchema, admin_profile = Depends(require_role(["admin"]))):
    if data.role not in ("doctor", "patient"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role must be either 'doctor' or 'patient'")

    try:
        res = supabase_admin.auth.admin.create_user({
            "email": data.email,
            "password": data.password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": data.full_name,
                "role": data.role
            }
        })

        if not res.user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create account")

        log_activity(
            user_id=admin_profile["id"],
            user_name=admin_profile["full_name"],
            role="admin",
            action="Admin Created Account",
            details=f"Created {data.role} account for {data.full_name} ({data.email})"
        )

        return {"message": f"{data.role.capitalize()} account created successfully", "user_id": res.user.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
