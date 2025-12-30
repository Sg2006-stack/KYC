import sys
import io
import logging
from pathlib import Path

_this_file = Path(__file__).resolve()
_project_root = _this_file.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from KYC.ocr_check import extract_text
from KYC.aadhar_validation import extract_aadhaar_number, extract_dob, is_age_above_18
from KYC.pan_validation import extract_pan_number
from KYC.face_match_selfie import match_faces, get_robust_encoding
from KYC.deepfake_detection import detect_deepfake
from KYC.email_notify import send_kyc_email
from KYC.save_kyc import save_kyc
from KYC.database import users
from KYC.kyc_input_checks import validate_kyc_slots
import uuid
from datetime import datetime
from bson import ObjectId
app = FastAPI()

# Allow the web UI (file:// or http://localhost) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("kyc")


_ALLOWED_EXTS = {"jpg", "jpeg", "png"}


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
                "expected": "image/*",
            },
        )

    try:
        Image.open(io.BytesIO(content)).verify()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Corrupted or non-image file",
                "field": field,
                "filename": filename,
                "error": f"{type(e).__name__}: {e}",
            },
        )

    return ext
#--------JSON Serializer (datetime, ObjectId, nested)-------#
def _convert_value(v):
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, dict):
        return serialize(v)
    if isinstance(v, (list, tuple)):
        return [_convert_value(x) for x in v]
    return v


def serialize(record: dict):
    if not isinstance(record, dict):
        return record
    out = {}
    for k, v in record.items():
        out[k] = _convert_value(v)
    return out


# -------- GET KYC Data by Email -------- #
@app.get("/get-kyc/{email}")
def get_kyc(email: str):
    record = users.find_one({"email": email}, {"_id": 0})
    if not record:
        return {"error": "Email not found"}
    return serialize(record)


# -------- KYC Verification API -------- #
@app.post("/kyc-verify")
async def verify_kyc(aadhaar: UploadFile = File(...),
                    pan: UploadFile = File(...),
                    selfie: UploadFile = File(...),
                    email: str = Form(...)):

    base_dir = Path(__file__).resolve().parent
    try:
        aadhaar_bytes = await aadhaar.read()
        pan_bytes = await pan.read()
        selfie_bytes = await selfie.read()

        aadhaar_ext = _validate_image_bytes("aadhaar", aadhaar.filename, aadhaar.content_type, aadhaar_bytes)
        pan_ext = _validate_image_bytes("pan", pan.filename, pan.content_type, pan_bytes)
        selfie_ext = _validate_image_bytes("selfie", selfie.filename, selfie.content_type, selfie_bytes)
    except HTTPException as e:
        logger.warning("upload_validation_failed: %s", e.detail)
        raise

    aadhar_path = base_dir / f"uploads/aadhaar/{uuid.uuid4()}.{aadhaar_ext}"
    pan_path = base_dir / f"uploads/pan/{uuid.uuid4()}.{pan_ext}"
    selfie_path = base_dir / f"uploads/selfie/{uuid.uuid4()}.{selfie_ext}"

    for p in (aadhar_path.parent, pan_path.parent, selfie_path.parent):
        p.mkdir(parents=True, exist_ok=True)

    with open(aadhar_path, "wb") as f:
        f.write(aadhaar_bytes)
    with open(pan_path, "wb") as f:
        f.write(pan_bytes)
    with open(selfie_path, "wb") as f:
        f.write(selfie_bytes)

    # OCR + slot validation (prevents swapping Aadhaar/PAN/Selfie inputs)
    aadhar_text = extract_text(str(aadhar_path))
    aadhaar_no = extract_aadhaar_number(aadhar_text)
    dob = extract_dob(aadhar_text)
    age_status = is_age_above_18(dob) if dob else False

    pan_text = extract_text(str(pan_path))
    pan_no = extract_pan_number(pan_text)

    selfie_text = extract_text(str(selfie_path))
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
            detail={
                "message": "Invalid / mismatched uploads",
                "issues": issues,
                "expected": {
                    "aadhaar": "Aadhaar card image",
                    "pan": "PAN card image",
                    "selfie": "Face selfie (no document text)",
                },
            },
        )

    # Run deepfake detection on selfie
    deepfake_result = detect_deepfake(selfie_path)

    face_result = match_faces(pan_path, selfie_path)

    score = face_result.get("similarity_percent", 0)
    
    # Consider deepfake detection in final status
    is_deepfake = bool(deepfake_result.get("is_deepfake", False))
    status = "VERIFIED" if (score > 75 and age_status and not is_deepfake) else "REVIEW"
    
    if is_deepfake:
        status = "REJECTED - DEEPFAKE DETECTED"

    save_kyc(aadhaar_no, pan_no, dob, age_status, score, status, email)

    response = {
        "aadhaar_no": aadhaar_no,
        "pan_no": pan_no,
        "dob": dob,
        "age_verified": age_status,
        "similarity": score,
        "face_match": face_result.get("match", False),
        "deepfake_analysis": {
            "is_deepfake": deepfake_result.get("is_deepfake", False),
            "authenticity_score": deepfake_result.get("authenticity_score", 0),
            "confidence": deepfake_result.get("confidence", 0),
            "status": deepfake_result.get("status", "Unknown"),
            "recommendation": deepfake_result.get("recommendation", "")
        },
        "final_status": status,
        "email": email
    }

    # Email notification (non-blocking for overall KYC success)
    email_result = send_kyc_email(to_email=email, report=response)
    response["email_notification"] = email_result

    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
