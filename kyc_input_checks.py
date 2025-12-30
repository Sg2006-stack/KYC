import re
from typing import Any, Dict, List, Optional


_PAN_RE = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")
_AADHAAR_RE = re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b|\b\d{12}\b")


def _alnum_len(s: str) -> int:
    return len(re.sub(r"[^A-Za-z0-9]", "", s or ""))


def looks_like_pan_text(text: str) -> bool:
    if not text:
        return False
    return bool(_PAN_RE.search(text.upper()))


def looks_like_aadhaar_text(text: str) -> bool:
    if not text:
        return False
    return bool(_AADHAAR_RE.search(text))


def selfie_looks_like_document(text: str) -> bool:
    """If selfie OCR contains strong ID patterns or lots of text, it's probably a document photo."""
    if not text:
        return False

    t = text.upper()
    if looks_like_pan_text(t) or looks_like_aadhaar_text(t):
        return True

    # Heuristic: selfies usually have very little machine-readable text.
    # If OCR returns lots of alnum characters, it's likely a card/document.
    return _alnum_len(t) >= 35


def validate_kyc_slots(
    *,
    aadhaar_no: Optional[str],
    dob: Optional[str],
    pan_no: Optional[str],
    selfie_text: str,
    selfie_has_face: bool,
) -> List[str]:
    issues: List[str] = []

    # Aadhaar slot: must have an Aadhaar number and DOB.
    if not aadhaar_no or not dob:
        issues.append(
            "Aadhaar upload does not look like an Aadhaar card (Aadhaar number/DOB not detected)."
        )

    # PAN slot: must have PAN number.
    if not pan_no:
        issues.append("PAN upload does not look like a PAN card (PAN number not detected).")

    # Selfie slot: must contain a face and should not look like a document.
    if not selfie_has_face:
        issues.append("Selfie upload must be a clear face photo (no face detected).")

    if selfie_looks_like_document(selfie_text):
        issues.append(
            "Selfie upload looks like an ID/document photo (text/ID patterns detected). Please upload a real face selfie."
        )

    return issues
