import re

def extract_pan_number(text):
    pattern = r"[A-Z]{5}[0-9]{4}[A-Z]"
    match = re.search(pattern, text)
    return match.group() if match else None

def is_valid_pan(pan_number):
    if not pan_number:
        return False

    # PAN Format rule: ABCDE1234F
    return bool(re.match(r"[A-Z]{5}[0-9]{4}[A-Z]", pan_number))

