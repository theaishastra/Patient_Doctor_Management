from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from database import supabase, supabase_admin
from config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()

# Pydantic Schemas
class RegisterSchema(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str # 'doctor' or 'patient'

class LoginSchema(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordSchema(BaseModel):
    email: EmailStr

class ResetPasswordSchema(BaseModel):
    access_token: str
    new_password: str

# Dependencies
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        # Validate the JWT via Supabase client
        # In newer python supabase-py versions, auth.get_user takes JWT as parameter
        res = supabase.auth.get_user(token)
        if not res or not res.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        return res.user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )

async def get_current_profile(user = Depends(get_current_user)):
    try:
        # Use supabase_admin to read profiles if needed, or normal client
        # public.profiles is readable by authenticated users
        res = supabase.table("profiles").select("*").eq("id", user.id).execute()
        if not res.data or len(res.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found in database"
            )
        return res.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

def require_role(allowed_roles: list[str]):
    async def dependency(profile = Depends(get_current_profile)):
        if profile["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(allowed_roles)}"
            )
        return profile
    return dependency

# Helper function to log activities
def log_activity(user_id: str, user_name: str, role: str, action: str, details: str = None):
    try:
        supabase_admin.table("activity_logs").insert({
            "user_id": user_id,
            "user_name": user_name,
            "role": role,
            "action": action,
            "details": details
        }).execute()
    except Exception as e:
        print(f"Error writing activity log: {str(e)}")

# Endpoints
@router.post("/register")
async def register(data: RegisterSchema):
    if data.role not in ["doctor", "patient"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be either 'doctor' or 'patient'"
        )
    
    try:
        # Sign up using Supabase Auth. This will invoke the database trigger
        res = supabase.auth.sign_up({
            "email": data.email,
            "password": data.password,
            "options": {
                "data": {
                    "full_name": data.full_name,
                    "role": data.role
                }
            }
        })
        
        if not res.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration failed"
            )

        # Auto-confirm the email so the user can log in immediately with
        # the credentials they just created, without waiting on a
        # verification email (Supabase's default email service is
        # rate-limited and unreliable).
        try:
            supabase_admin.auth.admin.update_user_by_id(res.user.id, {"email_confirm": True})
        except Exception as e:
            print(f"Error auto-confirming user email: {str(e)}")

        # Log registration activity
        log_activity(
            user_id=res.user.id,
            user_name=data.full_name,
            role=data.role,
            action="Register",
            details=f"User registered as a {data.role}"
        )

        return {"message": "Registration successful", "user_id": res.user.id}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/login")
async def login(data: LoginSchema):
    try:
        # Sign in with email and password
        res = supabase.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password
        })
        
        if not res.session or not res.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Login failed"
            )
        
        # Fetch the user's role from profile
        profile_res = supabase_admin.table("profiles").select("*").eq("id", res.user.id).execute()
        if not profile_res.data or len(profile_res.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found. Contact administrator."
            )
        
        profile = profile_res.data[0]
        
        # Log login activity
        log_activity(
            user_id=profile["id"],
            user_name=profile["full_name"],
            role=profile["role"],
            action="Login",
            details="User logged in successfully"
        )

        return {
            "access_token": res.session.access_token,
            "refresh_token": res.session.refresh_token,
            "user": {
                "id": profile["id"],
                "email": profile["email"],
                "full_name": profile["full_name"],
                "role": profile["role"]
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )

@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordSchema):
    try:
        supabase.auth.reset_password_for_email(
            data.email,
            {"redirect_to": settings.PASSWORD_RESET_REDIRECT_URL}
        )
    except Exception as e:
        # Don't leak whether the email exists; just log server-side
        print(f"Error sending password reset email: {str(e)}")

    return {"message": "If an account exists for this email, a password reset link has been sent."}

@router.post("/reset-password")
async def reset_password(data: ResetPasswordSchema):
    try:
        # Validate the recovery token and identify the user
        user_res = supabase.auth.get_user(data.access_token)
        if not user_res or not user_res.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired reset link. Please request a new one."
            )

        user_id = user_res.user.id

        # Update the password using the admin client
        supabase_admin.auth.admin.update_user_by_id(user_id, {"password": data.new_password})

        # Log the activity
        profile_res = supabase_admin.table("profiles").select("*").eq("id", user_id).execute()
        profile = profile_res.data[0] if profile_res.data else None
        log_activity(
            user_id=user_id,
            user_name=profile["full_name"] if profile else user_res.user.email,
            role=profile["role"] if profile else "unknown",
            action="Reset Password",
            details="User reset their password via email link"
        )

        return {"message": "Password has been reset successfully. You can now log in."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password reset failed: {str(e)}"
        )

@router.get("/me")
async def get_me(profile = Depends(get_current_profile)):
    return profile
