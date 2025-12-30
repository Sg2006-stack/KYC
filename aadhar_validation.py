import re
from datetime import datetime

def extract_aadhaar_number(text):
    match = re.search(r"\b\d{4}\s\d{4}\s\d{4}\b|\b\d{12}\b", text)
    return match.group().replace(" ", "") if match else None

def clean_possible_dob(text):
    repl = {
        'o': '0', 'O': '0',
        'b': '8', 'B': '8',
        's': '5', 'S': '5',
        'e': '6', 'E': '6',
        'l': '1', 'L': '1',
        'i': '1', 'I': '1',
        'z': '2', 'Z': '2'
    }
    for k, v in repl.items():
        text = text.replace(k, v)

    text = re.sub(r'[^0-9/\- ]', '', text)
    return text

def extract_dob(text):
    lines = text.splitlines()
    date_pattern = re.compile(r'(\d{1,2}[/-]\d{1,2}[/-]?\d{4})')

    for line in lines:
        if re.search(r'\b(dob|date of birth|dateofbirth|d\.o\.b)\b', line, re.I):
            candidates = _generate_date_candidates(line)
            for cand in candidates:
                m = date_pattern.search(cand)
                if m:
                    norm = _normalize_date(m.group(1))
                    try:
                        d, mo, y = norm.split('/')
                        di = int(d); mi = int(mo)
                        if 1 <= di <= 31 and 1 <= mi <= 12:
                            return norm
                    except:
                        continue
    all_matches = date_pattern.finditer(text)
    for m in all_matches:
        span_start = max(0, m.start() - 20)
        window = text[span_start:m.end() + 20]
        if re.search(r'issue|issued|printed|valid from|expiry|exp', window, re.I):
            continue
        return _normalize_date(m.group(1))

    return None


def _normalize_date(date_str):
    """Normalize date to DD/MM/YYYY. Accepts D/M/YYYY or D-M-YYYY."""
    date_str = date_str.replace('-', '/').strip()
    parts = date_str.split('/')
    if len(parts) == 3:
        d, m, y = parts
    elif len(parts) == 2 and len(parts[1]) == 6:
        d = parts[0]
        m = parts[1][:2]
        y = parts[1][2:]
    else:
        mobj = re.search(r'(\d{1,2})[/-]?(\d{1,2})[/-]?(\d{4})', date_str)
        if not mobj:
            return date_str
        d, m, y = mobj.group(1), mobj.group(2), mobj.group(3)
    d = d.zfill(2)
    m = m.zfill(2)
    return f"{d}/{m}/{y}"


def _generate_date_candidates(raw_line, max_comb=64):
    amb = {
        'o': ['0'], 'O': ['0'],
        'b': ['8'], 'B': ['8'],
        's': ['5', '8'], 'S': ['5', '8'],
        'e': ['8', '6'], 'E': ['8', '6'],
        'l': ['1'], 'L': ['1'],
        'i': ['1'], 'I': ['1'],
        'z': ['2'], 'Z': ['2']
    }

    chars = list(raw_line)
    indices = [i for i, ch in enumerate(chars) if ch in amb]
    # limit combinations
    if not indices:
        return [clean_possible_dob(raw_line)]

    from itertools import product
    choices = [amb[chars[i]] for i in indices]
    candidates = []
    for combo in product(*choices):
        for idx, repl in zip(indices, combo):
            chars[idx] = repl
        cand = ''.join(chars)
        candidates.append(clean_possible_dob(cand))
        if len(candidates) >= max_comb:
            break

    # also include a fully cleaned original as fallback
    candidates.append(clean_possible_dob(raw_line))
    return candidates


def is_age_above_18(dob_str):
    try:
        dob_clean = dob_str.replace('-', '/')
        dob = datetime.strptime(dob_clean, "%d/%m/%Y")
        age = (datetime.now() - dob).days // 365
        return age >= 18
    except:
        return False


def extract_gender(text):
    if "Male" in text:
        return "Male"
    if "Female" in text:
        return "Female"
    return None


