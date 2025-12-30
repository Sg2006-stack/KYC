import sys
import io
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from bson import ObjectId

from KYC.database import users
from KYC.save_kyc import save_kyc
from KYC.kyc_input_checks import validate_kyc_slots
from KYC.aadhar_validation import extract_aadhaar_number, extract_dob, is_age_above_18
from KYC.pan_validation import extract_pan_number
from KYC.email_notify import send_kyc_email


# ---------- PATH SETUP ----------
_this_file = Path(__file__).resolve()
_project_root = _this_file.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ---------- APP ----------
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


# ---------- SERIALIZER ----------
def _convert(v):
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, dict):
        return {k: _convert(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_convert(x) for x in v]
    return v


def serialize(record: dict):
    return _convert(record)


# ---------- ROUTES ----------
@app.get("/get-kyc/{email}")
def get_kyc(email: str):
    record = users.find_one({"email": email}, {"_id": 0})
    if not record:
        return {"error": "Email not found"}
    return serialize(record)


@app.post("/kyc-verify")
async def verify_kyc(
    aadhaar: UploadFile = File(...),
    pan: UploadFile = File(...),
    selfie: UploadFile = File(...),
    email: str = Form(...)
):
    base_dir = Path(__file__).resolve().parent

    # ---------- SAFE ML IMPORTS ----------
    try:
        from KYC.ocr_check import extract_text
        from KYC.face_match_selfie import match_faces, get_robust_encoding
        from KYC.deepfake_detection import detect_deepfake
    except Exception:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "ML features are disabled in serverless environment",
                "status": "DEMO_MODE"
            }
        )

    # ---------- READ FILES ----------
    aadhaar_bytes = await aadhaar.read()
    pan_bytes = await pan.read()
    selfie_bytes = await selfie.read()

    aadhaar_ext = _validate_image_bytes("aadhaar", aadhaar.filename, aadhaar.content_type, aadhaar_bytes)
    pan_ext = _validate_image_bytes("pan", pan.filename, pan.content_type, pan_bytes)
    selfie_ext = _validate_image_bytes("selfie", selfie.filename, selfie.content_type, selfie_bytes)

    aadhaar_path = base_dir / f"uploads/aadhaar/{uuid.uuid4()}.{aadhaar_ext}"
    pan_path = base_dir / f"uploads/pan/{uuid.uuid4()}.{pan_ext}"
    selfie_path = base_dir / f"uploads/selfie/{uuid.uuid4()}.{selfie_ext}"

    for p in (aadhaar_path.parent, pan_path.parent, selfie_path.parent):
        p.mkdir(parents=True, exist_ok=True)

    aadhaar_path.write_bytes(aadhaar_bytes)
    pan_path.write_bytes(pan_bytes)
    selfie_path.write_bytes(selfie_bytes)

    # ---------- OCR ----------
    aadhaar_text = extract_text(str(aadhaar_path))
    pan_text = extract_text(str(pan_path))
    selfie_text = extract_text(str(selfie_path))

    aadhaar_no = extract_aadhaar_number(aadhaar_text)
    dob = extract_dob(aadhaar_text)
    age_verified = is_age_above_18(dob) if dob else False
    pan_no = extract_pan_number(pan_text)

    selfie_enc, _ = get_robust_encoding(str(selfie_path))
    selfie_has_face = selfie_enc is not None

    issues = validate_kyc_slots(
        aadhaar_no=aadhaar_no,
        dob=dob,
        pan_no=pan_no,
        selfie_text=selfie_text,
        selfie_has_face=selfie_has_face,
    )

    if issues:
        raise HTTPException(
            status_code=400,
            detail={"message": "Invalid uploads", "issues": issues},
        )

    # ---------- ANALYSIS ----------
    deepfake_result = detect_deepfake(selfie_path)
    face_result = match_faces(pan_path, selfie_path)

    similarity = face_result.get("similarity_percent", 0)
    is_deepfake = bool(deepfake_result.get("is_deepfake", False))

    status = "VERIFIED"
    if similarity < 75 or not age_verified:
        status = "REVIEW"
    if is_deepfake:
        status = "REJECTED - DEEPFAKE"

    save_kyc(aadhaar_no, pan_no, dob, age_verified, similarity, status, email)

    response = {
        "aadhaar_no": aadhaar_no,
        "pan_no": pan_no,
        "dob": dob,
        "age_verified": age_verified,
        "similarity": similarity,
        "deepfake_analysis": deepfake_result,
        "final_status": status,
        "email": email,
    }

    response["email_notification"] = send_kyc_email(email, response)

    return response


# ---------- LOCAL RUN ----------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
