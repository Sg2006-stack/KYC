import cv2
import numpy as np
import face_recognition
from typing import Optional, Tuple, Dict, Any


def preprocess_keep_aspect(image_path: str, max_side: int = 800) -> Optional[np.ndarray]:
    img = cv2.imread(image_path)
    if img is None:
        return None
    h, w = img.shape[:2]
    scale = max_side / max(h, w)
    new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
    img = cv2.resize(img, (new_w, new_h))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return img
def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a is None or b is None:
        return -1.0
    eps = 1e-10
    an = a / (np.linalg.norm(a) + eps)
    bn = b / (np.linalg.norm(b) + eps)
    return float(np.dot(an, bn))


def _largest_face_box(face_locations: list) -> Optional[Tuple[int, int, int, int]]:
    if not face_locations:
        return None
    areas = [abs((b - t) * (r - l)) for (t, r, b, l) in face_locations]
    idx = int(np.argmax(areas))
    return face_locations[idx]


def _crop_with_margin(image: np.ndarray, box: Tuple[int, int, int, int], margin: float = 0.25) -> np.ndarray:
    t, r, b, l = box
    h, w = image.shape[:2]
    bw = r - l
    bh = b - t
    m = int(max(bw, bh) * margin)
    x1 = max(0, l - m)
    y1 = max(0, t - m)
    x2 = min(w, r + m)
    y2 = min(h, b + m)
    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        return cv2.resize(image, (256, 256))
    return cv2.resize(crop, (256, 256))


def get_robust_encoding(image_path: str) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
    debug: Dict[str, Any] = {"path": image_path, "found_locations": 0, "used_model": None, "encodings_count": 0}
    image = preprocess_keep_aspect(image_path)
    if image is None:
        debug["error"] = "image_not_readable"
        return None, debug

    # try several detection strategies
    locs = face_recognition.face_locations(image, model="hog")
    debug["used_model"] = "hog"
    if not locs:
        locs = face_recognition.face_locations(image, number_of_times_to_upsample=1, model="hog")
    if not locs:
        try:
            locs = face_recognition.face_locations(image, model="cnn")
            debug["used_model"] = "cnn"
        except Exception:
            locs = []

    debug["found_locations"] = len(locs)
    if not locs:
        return None, debug

    box = _largest_face_box(locs)
    if box is None:
        return None, debug

    face_crop = _crop_with_margin(image, box)

    # Get face encoding directly without augmentations for consistency
    encs = face_recognition.face_encodings(face_crop)
    
    debug["encodings_count"] = len(encs)
    if not encs:
        return None, debug
    # Use the first encoding, normalized
    avg = encs[0] / (np.linalg.norm(encs[0]) + 1e-10)
    return avg, debug

def match_faces(pan_image: str, selfie_image: str, threshold: float = 0.6) -> Dict[str, Any]:
    pan_enc, pan_debug = get_robust_encoding(pan_image)
    selfie_enc, selfie_debug = get_robust_encoding(selfie_image)

    if pan_enc is None:
        return {"status": "failed", "error": "No face detected in PAN image", "debug": pan_debug}

    if selfie_enc is None:
        return {"status": "failed", "error": "No face detected in Selfie", "debug": selfie_debug}

    cos = _cosine_similarity(pan_enc, selfie_enc)
    similarity_percent = round(((cos + 1) / 2) * 100, 2)
    match = cos >= threshold

    return {
        "match": bool(match),
        "similarity_percent": similarity_percent,
        "cosine": round(cos, 4),
        "decision": "KYC Verified" if match else "Face Mismatch! Manual Review Needed",
    }
