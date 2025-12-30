from pathlib import Path
import re


def _require_ocr_libs():
    """
    Safely import OCR-related libraries.
    Returns (cv2, pytesseract) or (None, None) if unavailable.
    """
    try:
        import cv2
        import pytesseract
        return cv2, pytesseract
    except ImportError:
        return None, None


def extract_text_from_image(image_path):
    """
    Extract raw text from an image using OCR.
    """
    cv2, pytesseract = _require_ocr_libs()
    if cv2 is None or pytesseract is None:
        return {
            "status": "disabled",
            "reason": "OCR not available in this environment",
            "text": ""
        }

    img = cv2.imread(str(image_path))
    if img is None:
        return {
            "error": "Could not read image",
            "text": ""
        }

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    text = pytesseract.image_to_string(gray)
    return {
        "status": "success",
        "text": text.strip()
    }


def extract_numbers(text):
    """
    Extract numeric sequences from OCR text (useful for IDs).
    """
    if not text:
        return []

    return re.findall(r"\d+", text)


def extract_pan_like(text):
    """
    Extract PAN-like patterns: 5 letters + 4 digits + 1 letter
    Example: ABCDE1234F
    """
    if not text:
        return []

    pattern = r"[A-Z]{5}[0-9]{4}[A-Z]"
    return re.findall(pattern, text.upper())


def extract_aadhaar_like(text):
    """
    Extract Aadhaar-like numbers: 12-digit numeric sequences
    """
    if not text:
        return []

    pattern = r"\b\d{4}\s?\d{4}\s?\d{4}\b"
    return re.findall(pattern, text)


def run_ocr_checks(image_path):
    """
    Main OCR pipeline used by KYC.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        return {
            "error": "Image file not found",
            "status": "failed"
        }

    ocr_result = extract_text_from_image(image_path)

    if ocr_result.get("status") != "success":
        return ocr_result

    text = ocr_result.get("text", "")

    return {
        "status": "success",
        "raw_text": text,
        "numbers_detected": extract_numbers(text),
        "pan_candidates": extract_pan_like(text),
        "aadhaar_candidates": extract_aadhaar_like(text)
    }


# Local testing only
if __name__ == "__main__":
    test_image = "uploads/ocr_test.jpg"
    result = run_ocr_checks(test_image)
    print(result)
