from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pathlib import Path
import os
import uuid
from PIL import Image

# ✅ CREATE APP FIRST
app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
ALLOWED_EXTENSIONS = {"jpeg"}

for folder in ["aadhaar", "pan", "selfie"]:
    (UPLOAD_DIR / folder).mkdir(parents=True, exist_ok=True)

# -------------------- FRONTEND --------------------

@app.get("/", response_class=HTMLResponse)
def serve_ui():
    html_path = BASE_DIR / "index.html"
    if not html_path.exists():
        return "<h1>index.html not found</h1>"
    return html_path.read_text(encoding="utf-8")

# -------------------- HELPERS --------------------

def validate_image(file: UploadFile):
    if "." not in file.filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    ext = file.filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only JPEG images are accepted")

    try:
        Image.open(file.file).verify()
        file.file.seek(0)
    except Exception:
        raise HTTPException(status_code=400, detail="Corrupted image")


def save_file(file: UploadFile, folder: str):
    ext = file.filename.rsplit(".", 1)[1]
    filename = f"{uuid.uuid4()}.{ext}"
    path = UPLOAD_DIR / folder / filename

    with open(path, "wb") as f:
        f.write(file.file.read())

    return str(path)

# -------------------- API --------------------

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
