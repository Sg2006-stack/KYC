from .database import users
from datetime import datetime
import json
from pathlib import Path
from bson import ObjectId

def save_kyc(aadhaar, pan, dob, age_status, face_score, status, email):
    data = {
        "aadhaar": aadhaar,
        "pan": pan,
        "dob": dob,
        "age_verified": age_status,
        "face_score": face_score,
        "kyc_status": status,
        "email": email,
        "timestamp": datetime.utcnow().isoformat()  # still safe
    }

    result = users.insert_one(data)
    data["_id"] = str(result.inserted_id)   # <<< convert ObjectId to string for JSON

    save_dir = Path("kyc_json")
    save_dir.mkdir(exist_ok=True)
    
    safe_email = str(email).strip().replace("@", "_at_").replace(".", "_")
    file_path = save_dir / f"KYC_{safe_email}.json"
    with open(file_path, "w") as json_file:
        json.dump(data, json_file, indent=4)

    return {"saved": True, "status": status, "file": str(file_path)}
