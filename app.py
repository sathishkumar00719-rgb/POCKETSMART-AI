"""
PocketSmart AI - Your Smart Budget & Recommendation Assistant
Main FastAPI application: page routes, auth routes, and the three
planner APIs (Home / Party / Jewelry), all wired to ai_service.py.

Run with:  uvicorn app:app --reload
Then open: http://127.0.0.1:8000
"""
import os
import json
import shutil
import uuid
from datetime import timedelta, datetime
from typing import Optional
import hashlib
import secrets
from fastapi import FastAPI, Request, Depends, HTTPException, status, Form, File, UploadFile
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from dotenv import load_dotenv
import random
import smtplib
from email.message import EmailMessage
from pydantic import BaseModel
from database import init_db, get_db_connection 
from models import (
    RegisterUser, UserInDB, Token,
    HomeBudgetInput, PartyBudgetInput, JewelryBudgetInput,
)

from auth import (
    blacklisted_tokens,
    get_password_hash, authenticate_user, create_access_token,
    get_current_user, get_current_active_user,
    ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM,
)

from storage import (
    active_sessions, user_recommendations,
    save_to_history, get_history, get_recommendation_by_id, touch_session,
)
from ai_service import (
    get_home_recommendations, get_party_recommendations, get_jewelry_recommendations,
    GENAI_AVAILABLE,
)

load_dotenv()
def send_otp_email(email, otp):
    sender_email = os.getenv("EMAIL_ADDRESS")
    sender_password = os.getenv("EMAIL_PASSWORD")

    if not sender_email or not sender_password:
        raise HTTPException(
            status_code=500,
            detail="Email configuration is missing"
        )

    msg = EmailMessage()

    msg["Subject"] = "PocketSmart AI - Email Verification OTP"
    msg["From"] = sender_email
    msg["To"] = email

    msg.set_content(
        f"""
Hello,

Your PocketSmart AI verification OTP is:

{otp}

This OTP is valid for 1 minute.

If you did not request this OTP, please ignore this email.

Regards,
PocketSmart AI
"""
    )

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)

app = FastAPI(title="PocketSmart AI: Your Smart Budget & Recommendation Assistant")

@app.on_event("startup")
async def startup_event():
    init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(
    directory=os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates"
    )
)
print("TEMPLATE PATH:", templates.env.loader.searchpath)

# Starlette's Jinja2Templates doesn't register Flask's `tojson` filter by
# default - add it so history.html can pretty-print the full JSON result.
templates.env.filters["tojson"] = lambda obj, indent=2: json.dumps(obj, indent=indent, default=str)


@app.exception_handler(StarletteHTTPException)
async def auth_redirect_handler(request: Request, exc: StarletteHTTPException):
    """
    If a protected *page* (not an API call) is hit without being logged in,
    redirect to /login instead of returning a raw 401 JSON error.
    API routes (fetch calls from the frontend JS) still get JSON errors.
    """
    if exc.status_code == 401 and "application/json" not in request.headers.get("accept", ""):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def save_upload_file(upload_file: UploadFile) -> str:
    ext = os.path.splitext(upload_file.filename)[1] or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join("static", "uploads", filename)
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return dest_path


# =========================================================================
# PAGE ROUTES
# =========================================================================

@app.get("/")
async def index(request: Request):
    current_user = await get_current_user(request)
    return templates.TemplateResponse(request,"index.html", {"request": request, "user": current_user})


@app.get("/login")
async def login_page(request: Request):
    current_user = await get_current_user(request)
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request, "login.html", {"request": request, "user": None})

@app.get("/forgot-password")
async def forgot_password_page(request: Request):

    return templates.TemplateResponse(
        request, "forgot_password.html",
        {
            "request": request
        }
    )

@app.get("/register")
async def register_page(request: Request):
    current_user = await get_current_user(request)
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request, "register.html", {"request": request, "user": None})


@app.get("/dashboard")
async def dashboard(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    history = get_history(current_user.username)[:5]
    return templates.TemplateResponse(
        request, "dashboard.html",
        {"request": request, "user": current_user, "recent": history},
    )


@app.get("/home-planner")
async def home_planner(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    return templates.TemplateResponse(request, "home_planner.html", {"request": request, "user": current_user})


@app.get("/party-planner")
async def party_planner(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    return templates.TemplateResponse(request, "party_planner.html", {"request": request, "user": current_user})


@app.get("/jewelry-planner")
async def jewelry_planner(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    return templates.TemplateResponse(request, "jewelry_planner.html", {"request": request, "user": current_user})


@app.get("/history")
async def history_page(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    history = get_history(current_user.username)
    return templates.TemplateResponse(request, "history.html", {"request": request, "user": current_user, "history": history})


# =========================================================================
# AUTH ROUTES
# =========================================================================
@app.post("/register")
async def register(user: RegisterUser):

    conn = get_db_connection()

    # Check existing username
    existing_username = conn.execute(
        "SELECT id FROM users WHERE username = ?",
        (user.username,)
    ).fetchone()

    if existing_username:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Username already registered"
        )

    # Check existing email
    existing_email = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        (user.email,)
    ).fetchone()

    if existing_email:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    # Remove old pending registration
    conn.execute(
        """
        DELETE FROM pending_users
        WHERE username = ? OR email = ?
        """,
        (user.username, user.email)
    )

    conn.commit()
    conn.close()

    # Hash password
    hashed_password = get_password_hash(user.password)

    # Generate 6 digit OTP
    otp = str(random.randint(100000, 999999))

    # Hash OTP
    otp_hash = hashlib.sha256(
        otp.encode()
    ).hexdigest()

    # OTP expires after 1 minute
    otp_expires_at = (
        datetime.utcnow() + timedelta(minutes=1)
    )

    # Send OTP email FIRST
    try:

        send_otp_email(
            user.email,
            otp
        )

    except Exception as e:

        print("OTP EMAIL ERROR:", e)

        raise HTTPException(
            status_code=500,
            detail="Unable to send OTP. Please check email configuration."
        )

    # Save pending registration only after email succeeds
    conn = get_db_connection()

    try:

        conn.execute(
            """
            INSERT INTO pending_users
            (
                username,
                email,
                full_name,
                hashed_password,
                otp_hash,
                otp_expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user.username,
                user.email,
                user.full_name,
                hashed_password,
                otp_hash,
                otp_expires_at
            )
        )

        conn.commit()

    except Exception as e:

        conn.rollback()

        print("PENDING USER ERROR:", e)

        raise HTTPException(
            status_code=500,
            detail="Unable to start registration"
        )

    finally:

        conn.close()

    return {
        "message": "OTP sent to your email. Please check your inbox."
    }


# =========================================
# VERIFY OTP
# =========================================

@app.post("/verify-otp")
async def verify_otp(data: dict):

    username = data.get("username")
    otp = data.get("otp")

    # Check username and OTP
    if not username or not otp:

        raise HTTPException(
            status_code=400,
            detail="Username and OTP are required"
        )

    conn = get_db_connection()

    # Find pending registration
    pending_user = conn.execute(
        """
        SELECT * FROM pending_users
        WHERE username = ?
        """,
        (username,)
    ).fetchone()

    if pending_user is None:

        conn.close()

        raise HTTPException(
            status_code=400,
            detail="Registration session not found. Please register again."
        )

    # Check OTP expiry
    expires_at = datetime.fromisoformat(
        pending_user["otp_expires_at"]
    )

    if datetime.utcnow() > expires_at:

        conn.execute(
            """
            DELETE FROM pending_users
            WHERE username = ?
            """,
            (username,)
        )

        conn.commit()
        conn.close()

        raise HTTPException(
            status_code=400,
            detail="OTP expired. Please register again."
        )

    # Hash entered OTP
    entered_otp_hash = hashlib.sha256(
        otp.encode()
    ).hexdigest()

    # Check OTP
    if entered_otp_hash != pending_user["otp_hash"]:

        conn.close()

        raise HTTPException(
            status_code=400,
            detail="Invalid OTP"
        )

    # OTP correct → create account
    try:

        conn.execute(
            """
            INSERT INTO users
            (
                username,
                email,
                full_name,
                hashed_password,
                email_verified,
                disabled
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                pending_user["username"],
                pending_user["email"],
                pending_user["full_name"],
                pending_user["hashed_password"],
                1,
                0
            )
        )

        # Delete pending registration
        conn.execute(
            """
            DELETE FROM pending_users
            WHERE username = ?
            """,
            (username,)
        )

        conn.commit()

    except Exception as e:

        conn.rollback()

        print("ACCOUNT CREATION ERROR:", e)

        conn.close()

        raise HTTPException(
            status_code=500,
            detail="Unable to create account"
        )

    conn.close()

    return {
        "message": "Email verified successfully. Account created."
    }

@app.post("/forgot-password")
async def forgot_password(data: dict):

    email = data.get("email")

    if not email:
        raise HTTPException(
            status_code=400,
            detail="Email is required"
        )

    conn = get_db_connection()

    user = conn.execute(
        "SELECT id, email FROM users WHERE email = ?",
        (email,)
    ).fetchone()

    if user is None:
        conn.close()

        raise HTTPException(
            status_code=400,
            detail="Email address not registered"
        )

    # Remove old reset request
    conn.execute(
        "DELETE FROM password_reset_otps WHERE email = ?",
        (email,)
    )

    conn.commit()
    conn.close()

    # Generate OTP
    otp = str(random.randint(100000, 999999))

    otp_hash = hashlib.sha256(
        otp.encode()
    ).hexdigest()

    otp_expires_at = (
        datetime.utcnow() + timedelta(minutes=1)
    )

    # Send OTP
    try:

        send_otp_email(
            email,
            otp
        )

    except Exception as e:

        print("PASSWORD RESET OTP ERROR:", e)

        raise HTTPException(
            status_code=500,
            detail="Unable to send OTP. Please check email configuration."
        )

    # Save OTP
    conn = get_db_connection()

    try:

        conn.execute(
            """
            INSERT INTO password_reset_otps
            (
                email,
                otp_hash,
                otp_expires_at,
                verified
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                email,
                otp_hash,
                otp_expires_at,
                0
            )
        )

        conn.commit()

    except Exception as e:

        conn.rollback()

        print("PASSWORD RESET ERROR:", e)

        raise HTTPException(
            status_code=500,
            detail="Unable to start password reset"
        )

    finally:

        conn.close()

    return {
        "message": "OTP sent to your email."
    }

@app.post("/verify-reset-otp")
async def verify_reset_otp(data: dict):

    email = data.get("email")
    otp = data.get("otp")

    if not email or not otp:

        raise HTTPException(
            status_code=400,
            detail="Email and OTP are required"
        )

    conn = get_db_connection()

    reset_data = conn.execute(
        """
        SELECT *
        FROM password_reset_otps
        WHERE email = ?
        """,
        (email,)
    ).fetchone()

    if reset_data is None:

        conn.close()

        raise HTTPException(
            status_code=400,
            detail="Reset session not found. Please request a new OTP."
        )

    # Check expiry
    expires_at = datetime.fromisoformat(
        reset_data["otp_expires_at"]
    )

    if datetime.utcnow() > expires_at:

        conn.execute(
            """
            DELETE FROM password_reset_otps
            WHERE email = ?
            """,
            (email,)
        )

        conn.commit()
        conn.close()

        raise HTTPException(
            status_code=400,
            detail="OTP expired. Please request a new OTP."
        )

    # Hash entered OTP
    entered_otp_hash = hashlib.sha256(
        otp.encode()
    ).hexdigest()

    # Compare OTP
    if entered_otp_hash != reset_data["otp_hash"]:

        conn.close()

        raise HTTPException(
            status_code=400,
            detail="Invalid OTP"
        )

    # Generate secure reset token
    reset_token = secrets.token_urlsafe(32)

    reset_token_hash = hashlib.sha256(
        reset_token.encode()
    ).hexdigest()

    # Mark OTP as verified
    conn.execute(
        """
        UPDATE password_reset_otps
        SET verified = 1,
            reset_token_hash = ?
        WHERE email = ?
        """,
        (
            reset_token_hash,
            email
        )
    )

    conn.commit()
    conn.close()

    return {
        "message": "OTP verified successfully.",
        "reset_token": reset_token
    }

@app.post("/reset-password")
async def reset_password(data: dict):

    email = data.get("email")
    reset_token = data.get("reset_token")
    new_password = data.get("new_password")

    if not email or not reset_token or not new_password:

        raise HTTPException(
            status_code=400,
            detail="Required fields are missing"
        )

    if len(new_password) < 6:

        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters"
        )

    reset_token_hash = hashlib.sha256(
        reset_token.encode()
    ).hexdigest()

    conn = get_db_connection()

    reset_data = conn.execute(
        """
        SELECT *
        FROM password_reset_otps
        WHERE email = ?
        """,
        (email,)
    ).fetchone()

    if reset_data is None:

        conn.close()

        raise HTTPException(
            status_code=400,
            detail="Invalid password reset request"
        )

    # OTP must be verified
    if reset_data["verified"] != 1:

        conn.close()

        raise HTTPException(
            status_code=400,
            detail="Please verify OTP first"
        )

    # Check reset token
    if reset_data["reset_token_hash"] != reset_token_hash:

        conn.close()

        raise HTTPException(
            status_code=400,
            detail="Invalid password reset token"
        )

    # Hash new password
    new_password_hash = get_password_hash(
        new_password
    )

    try:

        # Replace old password
        conn.execute(
            """
            UPDATE users
            SET hashed_password = ?
            WHERE email = ?
            """,
            (
                new_password_hash,
                email
            )
        )

        # Delete reset request
        conn.execute(
            """
            DELETE FROM password_reset_otps
            WHERE email = ?
            """,
            (email,)
        )

        conn.commit()

    except Exception as e:

        conn.rollback()

        print("PASSWORD UPDATE ERROR:", e)

        conn.close()

        raise HTTPException(
            status_code=500,
            detail="Unable to change password"
        )

    conn.close()

    return {
        "message": "Password changed successfully."
    }

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    touch_session(user.username, access_token)

    response = JSONResponse(content={"access_token": access_token, "token_type": "bearer"})
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
    )
    return response


@app.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("access_token")
    if token:
        blacklisted_tokens.add(token)
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token")
    return response


# =========================================================================
# PLANNER APIs
# =========================================================================

@app.post("/generate-home")
async def generate_home(
    budget_input: HomeBudgetInput,
    current_user: UserInDB = Depends(get_current_active_user),
):
    """Generate home interior recommendations."""
    result = get_home_recommendations(budget_input)
    save_to_history(current_user.username, "home", budget_input.model_dump(), result)
    return result


@app.post("/generate-party")
async def generate_party(
    budget_input: PartyBudgetInput,
    current_user: UserInDB = Depends(get_current_active_user),
):
    """Generate party planning recommendations."""
    result = get_party_recommendations(budget_input)
    save_to_history(current_user.username, "party", budget_input.model_dump(), result)
    return result


@app.post("/generate-jewelry")
async def generate_jewelry(
    total_budget: float = Form(...),
    occasion: str = Form(...),
    preferences: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: UserInDB = Depends(get_current_active_user),
):
    """Generate jewelry recommendations, optionally analyzing an uploaded outfit image."""
    budget_input = JewelryBudgetInput(total_budget=total_budget, occasion=occasion, preferences=preferences)

    image_path = None
    if image is not None and image.filename:
        image_path = save_upload_file(image)

    result = get_jewelry_recommendations(budget_input, image_path)

    input_data = budget_input.model_dump()
    if image_path:
        input_data["image"] = image.filename
    save_to_history(current_user.username, "jewelry", input_data, result)
    return result


# =========================================================================
# HISTORY / SESSION APIs
# =========================================================================

@app.get("/recommendation-history")
async def recommendation_history(current_user: UserInDB = Depends(get_current_active_user)):
    history = get_history(current_user.username)
    return {"history": [h.model_dump() for h in history]}


@app.get("/recommendation-details/{recommendation_id}")
async def recommendation_details(recommendation_id: str, current_user: UserInDB = Depends(get_current_active_user)):
    record = get_recommendation_by_id(current_user.username, recommendation_id)
    if not record:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return record.model_dump()


@app.get("/session-info")
async def session_info(current_user: UserInDB = Depends(get_current_active_user)):
    session = active_sessions.get(current_user.username)
    if not session:
        raise HTTPException(status_code=404, detail="No active session found")
    return {
        "username": session.username,
        "login_time": session.login_time,
        "last_activity": session.last_activity,
    }


@app.get("/health")
async def health():
    """Simple health check - also reports whether Gemini is configured or running in mock mode."""
    return {"status": "ok", "ai_mode": "gemini" if GENAI_AVAILABLE else "mock (no GOOGLE_API_KEY set)"}


if __name__ == "__main__":
    import uvicorn
    print("Starting PocketSmart AI...")
    print(f"AI mode: {'Gemini' if GENAI_AVAILABLE else 'MOCK (set GOOGLE_API_KEY in .env for real AI output)'}")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)