import sys
import io
import logging
import uuid
import os
import re
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from PIL import Image

# Serverless-friendly: No MongoDB, No ML models (they're too heavy for Vercel)
# This is a minimal demo version for Vercel deployment

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("kyc")

_ALLOWED_EXTS = {"jpg", "jpeg", "png"}


# ---------- HELPERS ----------
def _file_ext(filename: str) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower().strip()


def _validate_image_bytes(field: str, filename: str, content_type: str, content: bytes) -> str:
    ext = _file_ext(filename)
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid file format",
                "field": field,
                "filename": filename,
                "allowed": sorted(_ALLOWED_EXTS),
            },
        )

    if content_type and not content_type.lower().startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid content type",
                "field": field,
                "filename": filename,
                "content_type": content_type,
            },
        )

    try:
        Image.open(io.BytesIO(content)).verify()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Corrupted or invalid image",
                "field": field,
                "filename": filename,
            },
        )

    return ext


def send_sms_notification(phone: str, report: dict) -> dict:
    """Send SMS via Twilio. Works on Vercel if env vars are set."""
    
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_phone = os.getenv("TWILIO_PHONE_NUMBER")
    
    # Validate phone
    if not phone or not re.match(r"^\+?[1-9]\d{1,14}$", phone.strip()):
        return {"sent": False, "detail": f"Invalid phone format: {phone}. Use +919876543210"}
    
    # Check config
    if not account_sid or not auth_token or not from_phone:
        return {"sent": False, "detail": "Twilio not configured. Add TWILIO_* env vars in Vercel settings."}
    
    # Create message
    status = report.get("status", "UNKNOWN")
    similarity = report.get("similarity", "N/A")
    message = f"KYC Verification Complete\nStatus: {status}\nFace Match: {similarity}"
    
    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        msg = client.messages.create(
            body=message,
            from_=from_phone,
            to=phone
        )
        return {"sent": True, "message_sid": msg.sid, "detail": f"SMS sent to {phone}"}
    except ImportError:
        return {"sent": False, "detail": "Twilio not installed. Add 'twilio' to requirements.txt"}
    except Exception as e:
        return {"sent": False, "detail": f"SMS failed: {type(e).__name__}: {str(e)}"}


# ---------- ROUTES ----------
@app.get("/", response_class=HTMLResponse)
def serve_ui():
    html_path = Path(__file__).parent.parent / "index.html"
    if not html_path.exists():
        return "<h1>index.html not found</h1>"
    return html_path.read_text(encoding="utf-8")


@app.post("/kyc-verify")
async def verify_kyc(
    aadhaar: UploadFile = File(...),
    pan: UploadFile = File(...),
    selfie: UploadFile = File(...),
    phone: str = Form(...)
):
    """
    Serverless Demo Version:
    - File validation only
    - No OCR (Tesseract not available on Vercel)
    - No Face Recognition (dlib/face_recognition too heavy)
    - No MongoDB storage
    - No email notifications
    """
    
    # ---------- READ & VALIDATE FILES ----------
    aadhaar_bytes = await aadhaar.read()
    pan_bytes = await pan.read()
    selfie_bytes = await selfie.read()

    aadhaar_ext = _validate_image_bytes("aadhaar", aadhaar.filename, aadhaar.content_type, aadhaar_bytes)
    pan_ext = _validate_image_bytes("pan", pan.filename, pan.content_type, pan_bytes)
    selfie_ext = _validate_image_bytes("selfie", selfie.filename, selfie.content_type, selfie_bytes)

    # ---------- SEND SMS NOTIFICATION ----------
    sms_result = send_sms_notification(phone, {
        "status": "VERIFIED (DEMO)",
        "similarity": "N/A (Demo Mode)",
        "note": "File validation successful"
    })

    # Return demo response (without ML processing on Vercel)
    response = {
        "status": "SUCCESS",
        "message": "Files validated successfully (DEMO MODE - ML features disabled on serverless)",
        "files_received": {
            "aadhaar": aadhaar.filename,
            "pan": pan.filename,
            "selfie": selfie.filename
        },
        "phone": phone,
        "note": "This is a demo deployment. Full ML pipeline (OCR, Face Recognition, Deepfake Detection) requires dedicated server with GPU support.",
        "sms_notification": sms_result
    }

    return response


# Vercel handler
app = app
