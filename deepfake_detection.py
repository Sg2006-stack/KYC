"""
Deepfake Detection Module using Computer Vision and Deep Learning
Detects AI-generated or manipulated faces in selfie images
"""

import numpy as np
from pathlib import Path

def _require_cv2():
    try:
        import cv2
        return cv2
    except ImportError:
        return None


def analyze_image_quality(image_path):
    cv2 = _require_cv2()
    if cv2 is None:
        return {"status": "disabled", "reason": "OpenCV not available"}

    img = cv2.imread(str(image_path))
    if img is None:
        return {"error": "Could not read image"}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    noise_level = np.std(gray)

    return {
        "sharpness": float(laplacian_var),
        "noise_level": float(noise_level),
    }


def detect_jpeg_artifacts(image_path):
    cv2 = _require_cv2()
    if cv2 is None:
        return 0.0

    img = cv2.imread(str(image_path))
    if img is None:
        return 0.0

    ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    y_channel = ycrcb[:, :, 0]
    dct = cv2.dct(np.float32(y_channel))

    high_freq = np.abs(
        dct[int(dct.shape[0] * 0.7):, int(dct.shape[1] * 0.7):]
    )
    return float(np.mean(high_freq))


def check_face_consistency(image_path):
    cv2 = _require_cv2()
    if cv2 is None:
        return {"status": "disabled", "consistency_score": 0.0}

    img = cv2.imread(str(image_path))
    if img is None:
        return {"error": "Could not read image"}

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    eye_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_eye.xml"
    )

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    if len(faces) == 0:
        return {"face_detected": False, "eyes_detected": 0, "consistency_score": 0.0}

    eyes_count = 0
    for (x, y, w, h) in faces:
        roi_gray = gray[y:y+h, x:x+w]
        eyes_count += len(eye_cascade.detectMultiScale(roi_gray))

    consistency = 1.0 if eyes_count == 2 else 0.5 if eyes_count > 0 else 0.0
    return {
        "face_detected": True,
        "eyes_detected": eyes_count,
        "consistency_score": consistency,
    }


def detect_color_anomalies(image_path):
    cv2 = _require_cv2()
    if cv2 is None:
        return 0.0

    img = cv2.imread(str(image_path))
    if img is None:
        return 0.0

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return float((np.std(hsv[:, :, 0]) +
                  np.std(hsv[:, :, 1]) +
                  np.std(hsv[:, :, 2])) / 3)
