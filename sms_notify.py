import os
import re
from typing import Any, Dict


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
        return


def send_kyc_sms(
    to_phone: str,
    report: Dict[str, Any],
) -> Dict[str, Any]:
    """Send a KYC report via SMS using Twilio.

    Configure via environment variables:
      - TWILIO_ACCOUNT_SID (required)
      - TWILIO_AUTH_TOKEN (required)
      - TWILIO_PHONE_NUMBER (required - your Twilio number)

    Returns: {sent: bool, detail?: str, message_sid?: str}
    """

    # Try loading from .env files
    here = os.path.dirname(os.path.abspath(__file__))
    _load_env_file(os.path.join(here, ".env"))
    _load_env_file(os.path.join(os.path.dirname(here), ".env"))

    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_phone = os.getenv("TWILIO_PHONE_NUMBER")

    # Validate phone number format
    if not to_phone or not re.match(r"^\+?[1-9]\d{1,14}$", to_phone.strip()):
        return {"sent": False, "detail": f"Invalid phone number format: {to_phone!r}. Use format: +919876543210"}

    if not account_sid or not auth_token or not from_phone:
        return {
            "sent": False,
            "detail": "SMS is not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER.",
        }

    final_status = report.get("final_status", "UNKNOWN")
    similarity = report.get("similarity", "N/A")
    
    # Keep SMS short (160 chars limit for single SMS)
    message = (
        f"KYC Verification Complete\n"
        f"Status: {final_status}\n"
        f"Face Match: {similarity}\n"
        f"Check email for full report."
    )

    try:
        from twilio.rest import Client
        
        client = Client(account_sid, auth_token)
        msg = client.messages.create(
            body=message,
            from_=from_phone,
            to=to_phone
        )
        
        return {
            "sent": True,
            "message_sid": msg.sid,
            "detail": f"SMS sent to {to_phone}"
        }
    except ImportError:
        return {
            "sent": False,
            "detail": "Twilio library not installed. Run: pip install twilio"
        }
    except Exception as e:
        return {
            "sent": False,
            "detail": f"SMS send failed: {type(e).__name__}: {e}",
            "config": {
                "from": from_phone,
                "to": to_phone,
            }
        }
