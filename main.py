from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
from PIL import Image

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}

for folder in ["aadhaar", "pan", "selfie"]:
    os.makedirs(os.path.join(UPLOAD_DIR, folder), exist_ok=True)


def validate_image(file: UploadFile):
    if "." not in file.filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    ext = file.filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid image format")

    try:
        Image.open(file.file).verify()
        file.file.seek(0)
    except Exception:
        raise HTTPException(status_code=400, detail="Corrupted image")


def save_file(file: UploadFile, folder: str):
    ext = file.filename.rsplit(".", 1)[1]
    unique_name = f"{uuid.uuid4()}.{ext}"
    path = os.path.join(UPLOAD_DIR, folder, unique_name)

    with open(path, "wb") as f:
        f.write(file.file.read())

    return path


@app.post("/upload-kyc-documents")
async def upload_kyc_documents(
    aadhaar: UploadFile = File(...),
    pan: UploadFile = File(...),
    selfie: UploadFile = File(...)
):
    validate_image(aadhaar)
    validate_image(pan)
    validate_image(selfie)

    aadhaar_path = save_file(aadhaar, "aadhaar")
    pan_path = save_file(pan, "pan")
    selfie_path = save_file(selfie, "selfie")

    return {
        "message": "Documents uploaded successfully",
        "files": {
            "aadhaar": aadhaar_path,
            "pan": pan_path,
            "selfie": selfie_path
        }
    }
