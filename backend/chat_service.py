import io
import mimetypes
import zipfile
from datetime import datetime
from uuid import uuid4
from typing import Optional

from fastapi import HTTPException, UploadFile, status

from database import supabase, supabase_admin
from routers.auth import log_activity

CHAT_BUCKET = "chat-media"


def ensure_chat_bucket():
    try:
        supabase_admin.storage.create_bucket(CHAT_BUCKET, options={"public": False})
    except Exception:
        pass


def verify_chat_access(assignment_id: str, profile: dict) -> dict:
    res = supabase_admin.table("assignments").select("*").eq("id", assignment_id).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat thread not found")

    assignment = res.data[0]

    if profile["role"] == "admin":
        return assignment
    if profile["role"] == "doctor" and assignment["doctor_id"] == profile["id"]:
        return assignment
    if profile["role"] == "patient" and assignment["patient_id"] == profile["id"]:
        return assignment

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this chat")


def list_chat_messages(assignment_id: str) -> list[dict]:
    res = supabase_admin.table("chat_messages").select("*").eq("assignment_id", assignment_id).order("created_at").execute()
    messages = res.data

    sender_ids = list({m["sender_id"] for m in messages})
    names = {}
    if sender_ids:
        profiles_res = supabase_admin.table("profiles").select("id, full_name").in_("id", sender_ids).execute()
        names = {p["id"]: p["full_name"] for p in profiles_res.data}

    result = []
    for m in messages:
        result.append({
            "id": m["id"],
            "assignment_id": m["assignment_id"],
            "sender_id": m["sender_id"],
            "sender_role": m["sender_role"],
            "sender_name": names.get(m["sender_id"], "Unknown"),
            "message_type": m["message_type"],
            "content": m["content"],
            "file_name": m["file_name"],
            "created_at": m["created_at"],
        })
    return result


async def create_chat_message(
    assignment_id: str,
    sender_id: str,
    sender_role: str,
    sender_name: str,
    content: Optional[str],
    file: Optional[UploadFile],
) -> dict:
    insert_data = {
        "assignment_id": assignment_id,
        "sender_id": sender_id,
        "sender_role": sender_role,
    }

    if file is not None:
        contents = await file.read()
        content_type = file.content_type or ""
        if content_type.startswith("image/"):
            message_type = "image"
        elif content_type.startswith("video/"):
            message_type = "video"
        elif content_type.startswith("audio/"):
            message_type = "audio"
        else:
            message_type = "file"

        clean_filename = (file.filename or "upload").replace(" ", "_")
        file_path = f"{assignment_id}/{uuid4().hex}_{clean_filename}"

        ensure_chat_bucket()
        supabase_admin.storage.from_(CHAT_BUCKET).upload(
            path=file_path,
            file=contents,
            file_options={"content-type": content_type or "application/octet-stream", "x-upsert": "true"}
        )

        insert_data["message_type"] = message_type
        insert_data["file_path"] = file_path
        insert_data["file_name"] = file.filename
        insert_data["content"] = None
    else:
        if not content or not content.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message content cannot be empty")
        insert_data["message_type"] = "text"
        insert_data["content"] = content

    res = supabase_admin.table("chat_messages").insert(insert_data).execute()
    message = res.data[0]

    return {
        "id": message["id"],
        "assignment_id": message["assignment_id"],
        "sender_id": message["sender_id"],
        "sender_role": message["sender_role"],
        "sender_name": sender_name,
        "message_type": message["message_type"],
        "content": message["content"],
        "file_name": message["file_name"],
        "created_at": message["created_at"],
    }


def get_chat_media(message_id: str, profile: dict) -> tuple[bytes, str, str]:
    res = supabase_admin.table("chat_messages").select("*").eq("id", message_id).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    message = res.data[0]
    verify_chat_access(message["assignment_id"], profile)

    if not message["file_path"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This message has no attachment")

    file_bytes = supabase_admin.storage.from_(CHAT_BUCKET).download(message["file_path"])
    content_type, _ = mimetypes.guess_type(message["file_name"])
    return file_bytes, content_type or "application/octet-stream", message["file_name"]


def build_chat_zip(assignment_id: str) -> io.BytesIO:
    res = supabase_admin.table("chat_messages").select("*").eq("assignment_id", assignment_id).order("created_at").execute()
    messages = res.data

    sender_ids = list({m["sender_id"] for m in messages})
    names = {}
    if sender_ids:
        profiles_res = supabase_admin.table("profiles").select("id, full_name").in_("id", sender_ids).execute()
        names = {p["id"]: p["full_name"] for p in profiles_res.data}

    buffer = io.BytesIO()
    used_media_names = set()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        transcript_lines = []
        for m in messages:
            sender_name = names.get(m["sender_id"], "Unknown")
            timestamp = m["created_at"]
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

            if m["message_type"] == "text":
                line = f"[{timestamp}] {sender_name} ({m['sender_role']}): {m['content']}"
            else:
                line = f"[{timestamp}] {sender_name} ({m['sender_role']}): [{m['message_type']}] {m['file_name']}"
            transcript_lines.append(line)

            if m["file_path"]:
                try:
                    file_bytes = supabase_admin.storage.from_(CHAT_BUCKET).download(m["file_path"])
                    media_name = m["file_name"]
                    if media_name in used_media_names:
                        media_name = f"{m['id'][:8]}_{media_name}"
                    used_media_names.add(media_name)
                    zf.writestr(f"media/{media_name}", file_bytes)
                except Exception as e:
                    transcript_lines.append(f"    (failed to export attachment: {str(e)})")

        zf.writestr("transcript.txt", "\n".join(transcript_lines))

    buffer.seek(0)
    return buffer


def change_own_password(profile: dict, current_password: str, new_password: str):
    try:
        verify = supabase.auth.sign_in_with_password({
            "email": profile["email"],
            "password": current_password
        })
    except Exception:
        verify = None

    if not verify or not verify.session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")

    supabase_admin.auth.admin.update_user_by_id(profile["id"], {"password": new_password})

    log_activity(
        user_id=profile["id"],
        user_name=profile["full_name"],
        role=profile["role"],
        action="Change Password",
        details="User changed their own password"
    )

    return {"message": "Password updated successfully"}
