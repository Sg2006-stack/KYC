import sys
import io
import logging
import uuid
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

_ALLOWED_EXTS = {"jpeg"}


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
    email: str = Form(...)
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

    # Return demo response (without ML processing on Vercel)
    response = {
        "status": "SUCCESS",
        "message": "Files validated successfully (DEMO MODE - ML features disabled on serverless)",
        "files_received": {
            "aadhaar": aadhaar.filename,
            "pan": pan.filename,
            "selfie": selfie.filename
        },
        "email": email,
        "note": "This is a demo deployment. Full ML pipeline (OCR, Face Recognition, Deepfake Detection) requires dedicated server with GPU support.",
        "email_notification": {
            "sent": False,
            "detail": "Email notifications disabled in serverless mode"
        }
    }

    return response


# Vercel handler
app = app
