import mimetypes
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from database import supabase_admin
from routers.auth import require_role, log_activity
import chat_service

router = APIRouter(prefix="/api/patient", tags=["patient"])

# Check if user is a patient
patient_dependency = Depends(require_role(["patient"]))

# Pydantic Schemas
class ProfileUpdateSchema(BaseModel):
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    contact_number: Optional[str] = None
    emergency_contact: Optional[str] = None

class ChangePasswordSchema(BaseModel):
    current_password: str
    new_password: str

# Endpoints
@router.get("/dashboard")
async def get_patient_dashboard(patient_profile = Depends(require_role(["patient"]))):
    patient_id = patient_profile["id"]
    try:
        # 1. Fetch patient details (DOB, blood group, etc.)
        pat_res = supabase_admin.table("patients").select("*").eq("id", patient_id).execute()
        patient_details = pat_res.data[0] if pat_res.data else {}

        # 2. Fetch assigned doctors
        docs_res = supabase_admin.table("assignments").select(
            "*, doctor:doctors(*, profiles(full_name, email))"
        ).eq("patient_id", patient_id).execute()

        assigned_doctors = []
        for item in docs_res.data:
            doctor = item.get("doctor", {})
            doc_profile = doctor.get("profiles", {}) if doctor else {}
            if doctor:
                assigned_doctors.append({
                    "id": doctor["id"],
                    "full_name": doc_profile.get("full_name", "Unknown"),
                    "email": doc_profile.get("email", ""),
                    "specialization": doctor.get("specialization"),
                    "contact_number": doctor.get("contact_number"),
                    "bio": doctor.get("bio")
                })

        # 3. Fetch treatments / prescriptions
        treats_res = supabase_admin.table("treatments").select(
            "*, doctor:doctors(profiles(full_name))"
        ).eq("patient_id", patient_id).order("created_at", desc=True).execute()

        treatments = []
        for treat in treats_res.data:
            doc_profile = treat.get("doctor", {}).get("profiles", {}) if treat.get("doctor") else {}
            treatments.append({
                "id": treat["id"],
                "doctor_id": treat["doctor_id"],
                "doctor_name": doc_profile.get("full_name", "Unknown Doctor"),
                "diagnosis": treat["diagnosis"],
                "treatment_plan": treat["treatment_plan"],
                "suggested_medicines": treat["suggested_medicines"],
                "notes": treat["notes"],
                "created_at": treat["created_at"]
            })

        return {
            "patient_info": {
                "id": patient_id,
                "full_name": patient_profile["full_name"],
                "email": patient_profile["email"],
                **patient_details
            },
            "assigned_doctors": assigned_doctors,
            "treatments": treatments
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.put("/profile")
async def update_patient_profile(data: ProfileUpdateSchema, patient_profile = Depends(require_role(["patient"]))):
    patient_id = patient_profile["id"]
    try:
        update_data = {}
        if data.date_of_birth is not None:
            update_data["date_of_birth"] = data.date_of_birth if data.date_of_birth != "" else None
        if data.gender is not None:
            update_data["gender"] = data.gender
        if data.blood_group is not None:
            update_data["blood_group"] = data.blood_group
        if data.contact_number is not None:
            update_data["contact_number"] = data.contact_number
        if data.emergency_contact is not None:
            update_data["emergency_contact"] = data.emergency_contact

        if not update_data:
            return {"message": "No changes to update"}

        res = supabase_admin.table("patients").update(update_data).eq("id", patient_id).execute()

        log_activity(
            user_id=patient_id,
            user_name=patient_profile["full_name"],
            role="patient",
            action="Update Profile",
            details="Patient updated personal details"
        )
        return {"message": "Profile updated successfully", "data": res.data[0]}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/documents")
async def list_documents(patient_profile = Depends(require_role(["patient"]))):
    patient_id = patient_profile["id"]
    try:
        res = supabase_admin.table("medical_documents").select("*").eq("patient_id", patient_id).order("uploaded_at", desc=True).execute()
        return res.data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/documents")
async def upload_document(
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    patient_profile = Depends(require_role(["patient"]))
):
    patient_id = patient_profile["id"]
    bucket_name = "medical-documents"
    
    # 1. Check/Create the Storage Bucket as private (handling gracefully if it exists)
    try:
        supabase_admin.storage.create_bucket(bucket_name, options={"public": False})
    except Exception:
        pass

    try:
        # Read file contents
        contents = await file.read()

        # Clean filename to avoid issues
        clean_filename = file.filename.replace(" ", "_")
        file_path = f"{patient_id}/{clean_filename}"

        # 2. Upload file to Supabase Storage
        upload_res = supabase_admin.storage.from_(bucket_name).upload(
            path=file_path,
            file=contents,
            file_options={"content-type": file.content_type, "x-upsert": "true"}
        )

        # 3. Save metadata to database (file_url left blank - files are served
        # through the app's authenticated /view endpoints, not a public URL)
        res = supabase_admin.table("medical_documents").insert({
            "patient_id": patient_id,
            "file_name": file.filename,
            "file_path": file_path,
            "file_url": "",
            "description": description
        }).execute()

        log_activity(
            user_id=patient_id,
            user_name=patient_profile["full_name"],
            role="patient",
            action="Upload Document",
            details=f"Uploaded document: {file.filename}"
        )

        return {"message": "Document uploaded successfully", "data": res.data[0]}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )

@router.get("/documents/{doc_id}/view")
async def view_document(doc_id: str, patient_profile = Depends(require_role(["patient"]))):
    patient_id = patient_profile["id"]
    bucket_name = "medical-documents"
    try:
        doc_res = supabase_admin.table("medical_documents").select("*").eq("id", doc_id).execute()
        if not doc_res.data:
            raise HTTPException(status_code=404, detail="Document not found")

        document = doc_res.data[0]
        if document["patient_id"] != patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only view your own documents."
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

@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, patient_profile = Depends(require_role(["patient"]))):
    patient_id = patient_profile["id"]
    bucket_name = "medical-documents"
    try:
        # Check if the document belongs to this patient
        doc_res = supabase_admin.table("medical_documents").select("*").eq("id", doc_id).execute()
        if not doc_res.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document = doc_res.data[0]
        if document["patient_id"] != patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only delete your own documents."
            )

        # Delete from Supabase Storage
        try:
            supabase_admin.storage.from_(bucket_name).remove([document["file_path"]])
        except Exception as se:
            print(f"Warning: Storage deletion failed or file not found: {str(se)}")

        # Delete from database
        supabase_admin.table("medical_documents").delete().eq("id", doc_id).execute()

        log_activity(
            user_id=patient_id,
            user_name=patient_profile["full_name"],
            role="patient",
            action="Delete Document",
            details=f"Deleted document: {document['file_name']}"
        )

        return {"message": "Document deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ==========================================
# CHAT
# ==========================================
@router.get("/chats")
async def list_chats(patient_profile = Depends(require_role(["patient"]))):
    try:
        res = supabase_admin.table("assignments").select(
            "*, doctor:doctors(*, profiles(full_name))"
        ).eq("patient_id", patient_profile["id"]).execute()

        chats = []
        for item in res.data:
            doctor = item.get("doctor", {})
            doc_profile = doctor.get("profiles", {}) if doctor else {}

            last_msg_res = supabase_admin.table("chat_messages").select(
                "content, message_type, created_at"
            ).eq("assignment_id", item["id"]).order("created_at", desc=True).limit(1).execute()
            last_msg = last_msg_res.data[0] if last_msg_res.data else None

            chats.append({
                "assignment_id": item["id"],
                "doctor_id": item["doctor_id"],
                "doctor_name": doc_profile.get("full_name", "Unknown"),
                "specialization": doctor.get("specialization") if doctor else None,
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
async def get_chat_messages(assignment_id: str, patient_profile = Depends(require_role(["patient"]))):
    chat_service.verify_chat_access(assignment_id, patient_profile)
    return chat_service.list_chat_messages(assignment_id)

@router.post("/chats/{assignment_id}/messages")
async def send_chat_message(
    assignment_id: str,
    content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    patient_profile = Depends(require_role(["patient"]))
):
    chat_service.verify_chat_access(assignment_id, patient_profile)
    message = await chat_service.create_chat_message(
        assignment_id, patient_profile["id"], "patient", patient_profile["full_name"], content, file
    )
    log_activity(
        user_id=patient_profile["id"],
        user_name=patient_profile["full_name"],
        role="patient",
        action="Send Chat Message",
        details=f"Sent a {message['message_type']} message in chat {assignment_id}"
    )
    return message

@router.get("/chats/messages/{message_id}/media")
async def get_chat_message_media(message_id: str, patient_profile = Depends(require_role(["patient"]))):
    file_bytes, content_type, file_name = chat_service.get_chat_media(message_id, patient_profile)
    return Response(content=file_bytes, media_type=content_type)

# ==========================================
# CREDENTIALS
# ==========================================
@router.post("/change-password")
async def change_password(data: ChangePasswordSchema, patient_profile = Depends(require_role(["patient"]))):
    return chat_service.change_own_password(patient_profile, data.current_password, data.new_password)
