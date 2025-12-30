"""
Deepfake Detection Module using Computer Vision and Deep Learning
Detects AI-generated or manipulated faces in selfie images
"""

import cv2
import numpy as np
from pathlib import Path


def analyze_image_quality(image_path):
    """Analyze image artifacts that might indicate manipulation"""
    img = cv2.imread(str(image_path))
    if img is None:
        return {"error": "Could not read image"}
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Calculate Laplacian variance (sharpness/blur detection)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # Calculate noise level using standard deviation
    noise_level = np.std(gray)
    
    return {
        "sharpness": float(laplacian_var),
        "noise_level": float(noise_level)
    }


def detect_jpeg_artifacts(image_path):
    """Detect compression artifacts common in deepfakes"""
    img = cv2.imread(str(image_path))
    if img is None:
        return 0.0
    
    # Convert to YCrCb color space
    ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    y_channel = ycrcb[:, :, 0]
    
    # Calculate DCT to find compression patterns
    dct = cv2.dct(np.float32(y_channel))
    
    # High frequency components indicate compression
    high_freq = np.abs(dct[int(dct.shape[0]*0.7):, int(dct.shape[1]*0.7):])
    artifact_score = float(np.mean(high_freq))
    
    return artifact_score


def check_face_consistency(image_path):
    """Check for inconsistencies in facial features"""
    img = cv2.imread(str(image_path))
    if img is None:
        return {"error": "Could not read image"}
    
    # Load face and eye cascade classifiers
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    
    if len(faces) == 0:
        return {"face_detected": False, "eyes_detected": 0, "consistency_score": 0.0}
    
    eyes_count = 0
    for (x, y, w, h) in faces:
        roi_gray = gray[y:y+h, x:x+w]
        eyes = eye_cascade.detectMultiScale(roi_gray)
        eyes_count = len(eyes)
    
    # Consistency: real faces should have 2 eyes detected
    consistency = 1.0 if eyes_count == 2 else 0.5 if eyes_count > 0 else 0.0
    
    return {
        "face_detected": True,
        "eyes_detected": eyes_count,
        "consistency_score": consistency
    }


def detect_color_anomalies(image_path):
    """Detect unusual color distributions that may indicate manipulation"""
    img = cv2.imread(str(image_path))
    if img is None:
        return 0.0
    
    # Convert to HSV
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # Calculate color distribution variance
    h_std = np.std(hsv[:, :, 0])
    s_std = np.std(hsv[:, :, 1])
    v_std = np.std(hsv[:, :, 2])
    
    # Natural images have certain color distribution patterns
    color_variance = (h_std + s_std + v_std) / 3
    
    return float(color_variance)


def calculate_deepfake_probability(metrics):
    """Calculate overall deepfake probability based on multiple metrics"""
    
    # Weight different factors - increased weight on artifacts and consistency
    weights = {
        'sharpness': 0.15,
        'noise': 0.20,
        'artifacts': 0.30,
        'consistency': 0.25,
        'color': 0.10
    }
    
    # Normalize and score each metric (1.0 = looks natural)
    # NOTE: These are heuristic scores; robust deepfake detection usually needs video/temporal cues.

    def bell_score(x: float, center: float, width: float) -> float:
        """Score close to 1 near center, decreasing to 0 as it moves away."""
        if width <= 0:
            return 0.0
        return max(0.0, 1.0 - min(abs(x - center) / width, 1.0))

    sharp = float(metrics.get('sharpness', 0) or 0)
    noise = float(metrics.get('noise_level', 0) or 0)
    artifacts = float(metrics.get('artifact_score', 0) or 0)
    consistency_score = float(metrics.get('consistency_score', 0) or 0)  # 0-1 range
    color_var = float(metrics.get('color_variance', 0) or 0)

    # AI-generated images often have:
    # - Too perfect sharpness (very high or suspiciously consistent)
    # - Too low noise (overly smooth)
    # - Unusual artifact patterns
    # - Perfect color distribution (too uniform)
    
    # Sharpness: Real photos typically 100-400, AI often >400 or <50
    sharpness_score = bell_score(sharp, center=200.0, width=180.0)
    # Penalize extremely high sharpness (common in AI)
    if sharp > 500:
        sharpness_score *= 0.5
    
    # Noise: Real photos have 15-35, AI often <10 (too smooth) or >40 (fake noise added)
    noise_score = bell_score(noise, center=25.0, width=15.0)
    # Heavily penalize suspiciously low noise
    if noise < 12:
        noise_score *= 0.4
    
    # Color variance: Real photos 35-60, AI often too uniform (<30) or too varied (>70)
    color_score = bell_score(color_var, center=45.0, width=20.0)
    if color_var < 30 or color_var > 70:
        color_score *= 0.6

    # Artifacts: Higher indicates heavy compression; AI images often have low artifacts
    artifact_score = bell_score(artifacts, center=8.0, width=10.0)
    # Penalize very low artifacts (suspiciously clean)
    if artifacts < 3:
        artifact_score *= 0.5
    
    # Calculate weighted authenticity score
    authenticity = (
        sharpness_score * weights['sharpness'] +
        noise_score * weights['noise'] +
        artifact_score * weights['artifacts'] +
        consistency_score * weights['consistency'] +
        color_score * weights['color']
    )
    
    # Convert to deepfake probability (inverse of authenticity)
    deepfake_probability = (1.0 - authenticity) * 100
    
    return deepfake_probability


def detect_deepfake(image_path):
    """
    Main function to detect if an image is a deepfake
    Returns comprehensive analysis with confidence score
    """
    image_path = Path(image_path)
    
    if not image_path.exists():
        return {
            "error": "Image file not found",
            "is_deepfake": None,
            "confidence": 0
        }
    
    # Run all detection algorithms
    quality_metrics = analyze_image_quality(image_path)
    artifact_score = detect_jpeg_artifacts(image_path)
    face_consistency = check_face_consistency(image_path)
    color_variance = detect_color_anomalies(image_path)
    
    # Combine all metrics
    all_metrics = {
        "sharpness": quality_metrics.get("sharpness", 0),
        "noise_level": quality_metrics.get("noise_level", 0),
        "artifact_score": artifact_score,
        "consistency_score": face_consistency.get("consistency_score", 0),
        "color_variance": color_variance,
        "face_detected": face_consistency.get("face_detected", False),
        "eyes_detected": face_consistency.get("eyes_detected", 0)
    }
    
    # Calculate deepfake probability
    deepfake_prob = calculate_deepfake_probability(all_metrics)
    
    # Determine if image is likely a deepfake (lowered threshold to 45% to be more strict)
    is_deepfake = deepfake_prob > 45.0
    confidence = deepfake_prob if is_deepfake else (100 - deepfake_prob)
    
    return {
        "is_deepfake": is_deepfake,
        "deepfake_probability": round(deepfake_prob, 2),
        "confidence": round(confidence, 2),
        "authenticity_score": round(100 - deepfake_prob, 2),
        "metrics": {
            "image_sharpness": round(all_metrics["sharpness"], 2),
            "noise_level": round(all_metrics["noise_level"], 2),
            "compression_artifacts": round(artifact_score, 2),
            "face_consistency": round(face_consistency.get("consistency_score", 0) * 100, 2),
            "color_variance": round(color_variance, 2)
        },
        "status": "SUSPICIOUS - Potential Deepfake" if is_deepfake else "AUTHENTIC - Real Image",
        "recommendation": "Manual review required" if is_deepfake else "Proceed with verification"
    }


# Example usage
if __name__ == "__main__":
    # Test with an image
    test_image = "uploads/selfie/test.jpg"
    result = detect_deepfake(test_image)
    print(f"Deepfake Detection Result: {result}")
