import os
import smtplib
from email.message import EmailMessage
from typing import Any, Dict, Optional
import re


def _load_env_file(path: str) -> None:
    """Minimal .env loader (no dependency). Does not overwrite existing env vars."""
    try:
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            for raw in f.readlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        # Don't fail KYC because a .env file is malformed.
        return


def _get_bool_env(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def send_kyc_email(
    to_email: str,
    report: Dict[str, Any],
    subject: str = "Your KYC Verification Report",
) -> Dict[str, Any]:
    """Send a KYC report email.

    Configure via environment variables:
      - SMTP_HOST (required)
      - SMTP_PORT (default 587)
      - SMTP_USERNAME (required)
      - SMTP_PASSWORD (required)
      - SMTP_FROM (default SMTP_USERNAME)
      - SMTP_USE_TLS (default true)

    Returns: {sent: bool, detail?: str}
    """

    # Try loading from .env files (safe: does not overwrite existing env vars).
    here = os.path.dirname(os.path.abspath(__file__))
    _load_env_file(os.path.join(here, ".env"))
    _load_env_file(os.path.join(os.path.dirname(here), ".env"))

    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM") or smtp_user
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    use_tls = _get_bool_env("SMTP_USE_TLS", True)
    use_ssl = _get_bool_env("SMTP_USE_SSL", False)

    if not to_email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", to_email.strip()):
        return {"sent": False, "detail": f"Invalid destination email: {to_email!r}"}

    if not smtp_host or not smtp_user or not smtp_pass or not smtp_from:
        return {
            "sent": False,
            "detail": "SMTP is not configured. Set SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD (and optionally SMTP_FROM/SMTP_PORT/SMTP_USE_TLS).",
        }

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = to_email

    final_status = report.get("final_status", "UNKNOWN")
    face_similarity = report.get("similarity", "N/A")
    deepfake = report.get("deepfake_analysis", {}) or {}

    body_lines = [
        "Hello,",
        "",
        "Your KYC verification has been processed.",
        "",
        f"Final status: {final_status}",
        f"Face similarity: {face_similarity}",
    ]

    if isinstance(deepfake, dict):
        body_lines.extend(
            [
                "",
                "Deepfake analysis:",
                f"- Is deepfake: {deepfake.get('is_deepfake', 'N/A')}",
                f"- Authenticity score: {deepfake.get('authenticity_score', 'N/A')}",
                f"- Confidence: {deepfake.get('confidence', 'N/A')}",
                f"- Status: {deepfake.get('status', 'N/A')}",
                f"- Recommendation: {deepfake.get('recommendation', 'N/A')}",
            ]
        )

    body_lines.extend(
        [
            "Regards,",
            "AI KYC System",
        ]
    )

    msg.set_content("\n".join(body_lines))

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20) as server:
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
                server.ehlo()
                if use_tls:
                    server.starttls()
                    server.ehlo()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        return {"sent": True}
    except Exception as e:
        return {
            "sent": False,
            "detail": f"Email send failed: {type(e).__name__}: {e}",
            "smtp": {
                "host": smtp_host,
                "port": smtp_port,
                "use_tls": use_tls,
                "use_ssl": use_ssl,
                "from": smtp_from,
                "to": to_email,
            },
        }
